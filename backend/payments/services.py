from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from rest_framework import serializers

from orders.models import Order

from .models import Payment


logger = logging.getLogger(__name__)


class PaymentRoutingService:
	"""Resolve a payment method to the processor that should handle it."""

	PAYMENT_METHOD_TO_PROVIDER = {
		"MPESA": Payment.Provider.PESAPAL,
		"AIRTEL": Payment.Provider.PESAPAL,
		"MASTERCARD": Payment.Provider.PESAPAL,
		"VISACARDS": Payment.Provider.PESAPAL,
	}

	@staticmethod
	def normalize_payment_method(payment_method: str | None) -> str:
		return str(payment_method or "").strip().upper().replace(" ", "_")

	@staticmethod
	def resolve_provider(payment_method: str | None) -> str:
		normalized_payment_method = PaymentRoutingService.normalize_payment_method(payment_method)
		provider = PaymentRoutingService.PAYMENT_METHOD_TO_PROVIDER.get(normalized_payment_method)
		if provider:
			return provider

		raise serializers.ValidationError(
			{"payment_method": [f"Payment method '{payment_method}' is not connected to a processor yet."]}
		)


class PesapalService:
	"""Pesapal V3 integration adapter for authentication and checkout creation."""

	AUTH_ENDPOINT = "/api/Auth/RequestToken"
	REGISTER_IPN_ENDPOINT = "/api/URLSetup/RegisterIPN"
	GET_IPN_LIST_ENDPOINT = "/api/URLSetup/GetIpnList"
	SUBMIT_ORDER_ENDPOINT = "/api/Transactions/SubmitOrderRequest"
	GET_TRANSACTION_STATUS_ENDPOINT = "/api/Transactions/GetTransactionStatus"

	REQUEST_TIMEOUT = (10, 30)
	CACHE_TTL_SECONDS = 60 * 60 * 24
	IPN_NOTIFICATION_TYPE = "GET"

	@staticmethod
	def _session() -> requests.Session:
		session = requests.Session()
		session.headers.update(
			{
				"Accept": "application/json",
				"Content-Type": "application/json",
			}
		)
		return session

	@staticmethod
	def _get_setting(name: str, *, required: bool = True, default: str = "") -> str:
		value = getattr(settings, name, default)
		if required and not value:
			raise serializers.ValidationError({"detail": [f"Missing required setting: {name}."]})
		return str(value)

	@staticmethod
	def _base_url() -> str:
		base_url = PesapalService._get_setting("PESAPAL_BASE_URL")
		return base_url.rstrip("/")

	@staticmethod
	def _build_url(endpoint: str) -> str:
		return f"{PesapalService._base_url()}{endpoint}"

	@staticmethod
	def _safe_provider_message(data: Any) -> str:
		if isinstance(data, dict):
			message = data.get("message")
			if isinstance(message, str) and message.strip():
				return message.strip()
		return "Payment provider request failed."

	@staticmethod
	def _cache_key_for_ipn(url: str) -> str:
		return f"pesapal:ipn_id:{url}"

	@staticmethod
	def _request(
		*,
		session: requests.Session,
		method: str,
		url: str,
		headers: dict[str, str] | None = None,
		payload: dict[str, Any] | None = None,
		error_context: str,
	) -> dict[str, Any] | list[Any]:
		try:
			response = session.request(
				method=method,
				url=url,
				headers=headers,
				json=payload,
				timeout=PesapalService.REQUEST_TIMEOUT,
			)
		except requests.Timeout as exc:
			logger.exception("Pesapal request timed out during %s", error_context)
			raise serializers.ValidationError({"detail": ["Payment provider timeout. Please retry."]}) from exc
		except requests.ConnectionError as exc:
			logger.exception("Pesapal connection error during %s", error_context)
			raise serializers.ValidationError({"detail": ["Payment provider is unreachable. Please retry."]}) from exc
		except requests.RequestException as exc:
			logger.exception("Pesapal transport error during %s", error_context)
			raise serializers.ValidationError({"detail": ["Unable to contact payment provider right now."]}) from exc

		response_data: Any
		try:
			response_data = response.json()
		except ValueError as exc:
			logger.error("Pesapal returned non-JSON response during %s with status %s", error_context, response.status_code)
			raise serializers.ValidationError({"detail": ["Unexpected response from payment provider."]}) from exc

		if response.status_code in (401, 403):
			logger.warning("Pesapal authorization failure during %s with status %s", error_context, response.status_code)
			raise serializers.ValidationError({"detail": ["Payment provider authentication failed."]})

		if response.status_code == 400:
			logger.warning("Pesapal validation failure during %s", error_context)
			message = PesapalService._safe_provider_message(response_data)
			raise serializers.ValidationError({"detail": [message]})

		if response.status_code >= 500:
			logger.error("Pesapal server failure during %s with status %s", error_context, response.status_code)
			raise serializers.ValidationError({"detail": ["Payment provider is temporarily unavailable."]})

		if response.status_code >= 300:
			logger.error("Pesapal unexpected status %s during %s", response.status_code, error_context)
			raise serializers.ValidationError({"detail": ["Payment provider request failed."]})

		return response_data

	@staticmethod
	def _authorization_header(token: str) -> dict[str, str]:
		return {"Authorization": f"Bearer {token}"}

	@staticmethod
	def _build_billing_address(order: Order) -> dict[str, Any]:
		name_parts = [part for part in order.customer_name.split(" ") if part]
		first_name = name_parts[0] if name_parts else "Customer"
		last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

		return {
			"phone_number": order.customer_phone or "",
			"email_address": order.customer_email,
			"country_code": PesapalService._get_setting("PESAPAL_COUNTRY_CODE", required=False, default="KE"),
			"first_name": first_name,
			"middle_name": "",
			"last_name": last_name,
			"line_1": (order.shipping_address or "").strip()[:120],
			"line_2": "",
			"city": "",
			"state": "",
			"postal_code": "",
			"zip_code": "",
		}

	@staticmethod
	def authenticate(*, session: requests.Session | None = None) -> str:
		"""Authenticate against Pesapal V3 and return bearer token."""

		consumer_key = PesapalService._get_setting("PESAPAL_CONSUMER_KEY")
		consumer_secret = PesapalService._get_setting("PESAPAL_CONSUMER_SECRET")
		session = session or PesapalService._session()

		logger.info("Authenticating with Pesapal")
		response_data = PesapalService._request(
			session=session,
			method="POST",
			url=PesapalService._build_url(PesapalService.AUTH_ENDPOINT),
			payload={
				"consumer_key": consumer_key,
				"consumer_secret": consumer_secret,
			},
			error_context="authenticate",
		)

		if not isinstance(response_data, dict):
			raise serializers.ValidationError({"detail": ["Invalid authentication response from payment provider."]})

		token = response_data.get("token")
		if not token:
			logger.error("Pesapal authentication response missing token")
			raise serializers.ValidationError({"detail": ["Failed to authenticate payment provider."]})

		logger.info("Pesapal authentication successful")
		return str(token)

	@staticmethod
	def register_ipn(*, session: requests.Session | None = None, token: str | None = None) -> str:
		"""Get or register IPN URL and return notification_id (ipn_id)."""

		ipn_url = PesapalService._get_setting("PESAPAL_IPN_URL")
		cache_key = PesapalService._cache_key_for_ipn(ipn_url)
		cached_ipn_id = cache.get(cache_key)
		if cached_ipn_id:
			return str(cached_ipn_id)

		session = session or PesapalService._session()
		access_token = token or PesapalService.authenticate(session=session)
		headers = PesapalService._authorization_header(access_token)

		logger.info("Checking existing Pesapal IPN registrations")
		ipn_list_response = PesapalService._request(
			session=session,
			method="GET",
			url=PesapalService._build_url(PesapalService.GET_IPN_LIST_ENDPOINT),
			headers=headers,
			error_context="get_ipn_list",
		)

		if isinstance(ipn_list_response, list):
			for ipn_entry in ipn_list_response:
				if not isinstance(ipn_entry, dict):
					continue
				if ipn_entry.get("url") == ipn_url and ipn_entry.get("ipn_notification_type") == PesapalService.IPN_NOTIFICATION_TYPE:
					ipn_id = ipn_entry.get("ipn_id")
					if ipn_id:
						cache.set(cache_key, str(ipn_id), PesapalService.CACHE_TTL_SECONDS)
						return str(ipn_id)

		logger.info("Registering Pesapal IPN URL")
		register_response = PesapalService._request(
			session=session,
			method="POST",
			url=PesapalService._build_url(PesapalService.REGISTER_IPN_ENDPOINT),
			headers=headers,
			payload={
				"url": ipn_url,
				"ipn_notification_type": PesapalService.IPN_NOTIFICATION_TYPE,
			},
			error_context="register_ipn",
		)

		if not isinstance(register_response, dict):
			raise serializers.ValidationError({"detail": ["Invalid IPN registration response from payment provider."]})

		ipn_id = register_response.get("ipn_id")
		if not ipn_id:
			error_data = register_response.get("error")
			if isinstance(error_data, dict) and error_data.get("code") == "duplicate_ipn_url":
				logger.info("Pesapal reported duplicate IPN URL, resolving via GetIpnList")
				cache.delete(cache_key)
				return PesapalService.register_ipn(session=session, token=access_token)
			raise serializers.ValidationError({"detail": ["Failed to register payment notification endpoint."]})

		cache.set(cache_key, str(ipn_id), PesapalService.CACHE_TTL_SECONDS)
		return str(ipn_id)

	@staticmethod
	def create_payment(order: Order, payment: Payment) -> dict[str, Any]:
		"""Create a Pesapal checkout session and return normalized payment details."""

		session = PesapalService._session()
		token = PesapalService.authenticate(session=session)
		notification_id = PesapalService.register_ipn(session=session, token=token)
		callback_url = PesapalService._get_setting("PESAPAL_CALLBACK_URL")

		description = f"Order {order.reference} payment"
		request_payload: dict[str, Any] = {
			"id": order.merchant_reference,
			"currency": order.currency,
			"amount": float(Decimal(order.total_amount).quantize(Decimal("0.01"))),
			"description": description[:100],
			"callback_url": callback_url,
			"notification_id": notification_id,
			"billing_address": PesapalService._build_billing_address(order),
		}

		redirect_mode = PesapalService._get_setting("PESAPAL_REDIRECT_MODE", required=False, default="").strip().upper()
		if redirect_mode in {"TOP_WINDOW", "PARENT_WINDOW"}:
			request_payload["redirect_mode"] = redirect_mode

		cancellation_url = PesapalService._get_setting("PESAPAL_CANCELLATION_URL", required=False, default="").strip()
		if cancellation_url:
			request_payload["cancellation_url"] = cancellation_url

		branch = PesapalService._get_setting("PESAPAL_BRANCH", required=False, default="").strip()
		if branch:
			request_payload["branch"] = branch

		logger.info("Submitting Pesapal order request for payment %s and order %s", payment.reference, order.reference)
		response_data = PesapalService._request(
			session=session,
			method="POST",
			url=PesapalService._build_url(PesapalService.SUBMIT_ORDER_ENDPOINT),
			headers=PesapalService._authorization_header(token),
			payload=request_payload,
			error_context="submit_order_request",
		)

		if not isinstance(response_data, dict):
			raise serializers.ValidationError({"detail": ["Invalid checkout response from payment provider."]})

		redirect_url = response_data.get("redirect_url")
		order_tracking_id = response_data.get("order_tracking_id")
		merchant_reference = response_data.get("merchant_reference")

		if not redirect_url or not order_tracking_id:
			logger.error("Pesapal submit order response missing required fields for payment %s", payment.reference)
			raise serializers.ValidationError({"detail": ["Unable to initialize checkout session."]})

		logger.info("Pesapal checkout initialized for payment %s", payment.reference)
		return {
			"provider": Payment.Provider.PESAPAL,
			"merchant_reference": merchant_reference or order.merchant_reference,
			"redirect_url": str(redirect_url),
			"provider_reference": merchant_reference or order.merchant_reference,
			"provider_tracking_id": str(order_tracking_id),
			"status": Payment.Status.PENDING,
			"request_payload": request_payload,
			"response_payload": response_data,
		}

	@staticmethod
	def verify_transaction(order_tracking_id: str) -> dict[str, Any]:
		"""Fetch latest transaction state from Pesapal for a tracking id."""

		session = PesapalService._session()
		token = PesapalService.authenticate(session=session)

		response_data = PesapalService._request(
			session=session,
			method="GET",
			url=f"{PesapalService._build_url(PesapalService.GET_TRANSACTION_STATUS_ENDPOINT)}?orderTrackingId={order_tracking_id}",
			headers=PesapalService._authorization_header(token),
			error_context="get_transaction_status",
		)

		if not isinstance(response_data, dict):
			raise serializers.ValidationError({"detail": ["Invalid transaction status response from payment provider."]})

		return response_data

class PaymentService:
	"""Application service for payment initiation and provider orchestration."""

	@staticmethod
	def _get_order(order_reference: str) -> Order:
		try:
			return Order.objects.prefetch_related("items").get(reference=order_reference)
		except Order.DoesNotExist as exc:
			raise serializers.ValidationError({"order_reference": ["Order not found."]}) from exc

	@staticmethod
	def _validate_order_for_payment(order: Order) -> None:
		if not order.items.exists():
			raise serializers.ValidationError({"order_reference": ["Cannot initiate payment for an empty order."]})
		if order.total_amount <= 0:
			raise serializers.ValidationError({"order_reference": ["Cannot initiate payment for an order with zero total."]})
		if order.status == Order.Status.PAID:
			raise serializers.ValidationError({"order_reference": ["This order has already been paid."]})
		if order.status == Order.Status.CANCELLED:
			raise serializers.ValidationError({"order_reference": ["Cancelled orders cannot be paid."]})

	@staticmethod
	def _get_provider_adapter(provider: str):
		if provider == Payment.Provider.PESAPAL:
			return PesapalService
		raise serializers.ValidationError({"provider": ["Unsupported payment provider."]})

	@staticmethod
	def _resolve_payment_for_notification(*, order_tracking_id: str, merchant_reference: str | None) -> Payment:
		payment = Payment.objects.select_related("order").filter(provider_tracking_id=order_tracking_id).first()
		if payment:
			return payment

		if merchant_reference:
			payment = Payment.objects.select_related("order").filter(provider_reference=merchant_reference).order_by("-created_at").first()
			if payment:
				return payment

		raise serializers.ValidationError({"detail": ["Payment record not found for provider notification."]})

	@staticmethod
	def _map_provider_status(status_payload: dict[str, Any]) -> tuple[str, str]:
		provider_status = str(status_payload.get("payment_status_description") or "").strip().lower()

		if "complete" in provider_status:
			return Payment.Status.COMPLETED, Order.Status.PAID
		if "cancel" in provider_status or "reverse" in provider_status:
			return Payment.Status.CANCELLED, Order.Status.CANCELLED
		if "fail" in provider_status or "declin" in provider_status or "invalid" in provider_status:
			return Payment.Status.FAILED, Order.Status.FAILED

		return Payment.Status.PENDING, Order.Status.PENDING

	@staticmethod
	@transaction.atomic
	def reconcile_pesapal_notification(
		*,
		order_tracking_id: str,
		merchant_reference: str | None = None,
		notification_type: str | None = None,
	) -> Payment:
		"""Reconcile callback/IPN events by verifying status and updating Payment/Order."""

		payment = PaymentService._resolve_payment_for_notification(
			order_tracking_id=order_tracking_id,
			merchant_reference=merchant_reference,
		)
		status_payload = PesapalService.verify_transaction(order_tracking_id)
		payment_status, order_status = PaymentService._map_provider_status(status_payload)

		merged_response = dict(payment.checkout_response or {})
		merged_response["transaction_status"] = status_payload
		if notification_type:
			merged_response["notification_type"] = notification_type

		payment.provider_tracking_id = order_tracking_id
		payment.status = payment_status
		payment.checkout_response = merged_response
		payment.save(update_fields=["provider_tracking_id", "status", "checkout_response", "updated_at"])

		order = payment.order
		order.pesapal_tracking_id = order_tracking_id
		order.status = order_status
		order.save(update_fields=["pesapal_tracking_id", "status", "updated_at"])

		return payment

	@staticmethod
	@transaction.atomic
	def initiate_payment(*, order_reference: str, provider: str) -> Payment:
		order = PaymentService._get_order(order_reference)
		PaymentService._validate_order_for_payment(order)
		resolved_provider = PaymentRoutingService.resolve_provider(order.payment_method or provider)

		try:
			payment = Payment.objects.create(
				order=order,
				provider=resolved_provider,
				amount=order.total_amount,
				currency=order.currency,
			)
			provider_adapter = PaymentService._get_provider_adapter(resolved_provider)
			provider_result = provider_adapter.create_payment(order, payment)

			payment.redirect_url = provider_result.get("redirect_url", "")
			payment.provider_reference = provider_result.get("provider_reference")
			payment.provider_tracking_id = provider_result.get("provider_tracking_id")
			payment.status = provider_result.get("status", Payment.Status.PENDING)
			payment.checkout_request = provider_result.get("request_payload", {})
			payment.checkout_response = provider_result.get("response_payload", {})
			payment.save(
				update_fields=[
					"redirect_url",
					"provider_reference",
					"provider_tracking_id",
					"status",
					"checkout_request",
					"checkout_response",
					"updated_at",
				]
			)

			order.payment_method = PaymentRoutingService.normalize_payment_method(order.payment_method or provider)
			if payment.provider_tracking_id:
				order.pesapal_tracking_id = payment.provider_tracking_id
			order.save(update_fields=["payment_method", "pesapal_tracking_id", "updated_at"])

			return payment
		except serializers.ValidationError:
			raise
		except IntegrityError as exc:
			raise serializers.ValidationError({"detail": ["Unable to initialize payment right now."]}) from exc