from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import stripe
from django.conf import settings
from django.db import transaction
from rest_framework import serializers

from orders.models import Order

from .models import Payment

logger = logging.getLogger(__name__)


class StripeService:
	"""Stripe Checkout Session integration adapter for hosted checkout."""

	REQUEST_TIMEOUT = (10, 30)
	WEBHOOK_EVENTS = {"checkout.session.completed", "payment_intent.succeeded"}

	@staticmethod
	def _get_setting(name: str, *, required: bool = True, default: str = "") -> str:
		value = getattr(settings, name, default)
		if required and not value:
			raise serializers.ValidationError({"detail": [f"Missing required setting: {name}."]})
		return str(value)

	@staticmethod
	def _build_success_url(session_id: str) -> str:
		base_url = StripeService._get_setting("FRONTEND_PAYMENT_RESULT_URL", required=False, default="").strip()
		if not base_url:
			base_url = StripeService._get_setting("STRIPE_SUCCESS_URL", required=False, default="").strip()
		if base_url:
			separator = "&" if "?" in base_url else "?"
			return f"{base_url}{separator}session_id={session_id}"
		return ""

	@staticmethod
	def _build_cancel_url() -> str:
		return StripeService._get_setting("STRIPE_CANCEL_URL", required=False, default="").strip()

	@staticmethod
	def _normalize_currency(currency: str) -> str:
		return str(currency or "USD").strip().lower()

	@staticmethod
	def _coerce_mapping(value: Any) -> dict[str, Any]:
		if isinstance(value, dict):
			return dict(value)
		to_dict_recursive = getattr(value, "to_dict_recursive", None)
		if callable(to_dict_recursive):
			converted = to_dict_recursive()
			if isinstance(converted, dict):
				return converted
		return {}

	@staticmethod
	def _build_line_items(order: Order) -> list[dict[str, Any]]:
		if order.items.exists():
			items: list[dict[str, Any]] = []
			for item in order.items.all():
				unit_amount = int((Decimal(str(item.subtotal or item.unit_price)) * Decimal("100")).quantize(Decimal("1")))
				items.append(
					{
						"price_data": {
							"currency": StripeService._normalize_currency(order.currency),
							"product_data": {"name": str(item.product_name)[:250]},
							"unit_amount": unit_amount,
						},
						"quantity": int(item.quantity),
					}
				)
			if items:
				return items

		total_amount = int((Decimal(str(order.total_amount)) * Decimal("100")).quantize(Decimal("1")))
		return [
			{
				"price_data": {
					"currency": StripeService._normalize_currency(order.currency),
					"product_data": {"name": f"Order {order.reference}"},
					"unit_amount": total_amount,
				},
				"quantity": 1,
			}
		]

	@staticmethod
	def _get_api_key() -> str:
		return StripeService._get_setting("STRIPE_SECRET_KEY")

	@staticmethod
	def create_payment(order: Order, payment: Payment) -> dict[str, Any]:
		"""Create a Stripe Checkout Session and return normalized payment details."""
		stripe.api_key = StripeService._get_api_key()
		metadata = {
			"payment_reference": str(payment.reference),
			"order_reference": str(order.reference),
			"provider": Payment.Provider.STRIPE,
		}
		request_payload = {
			"mode": "payment",
			"success_url": StripeService._build_success_url("{CHECKOUT_SESSION_ID}"),
			"cancel_url": StripeService._build_cancel_url(),
			"customer_email": order.customer_email,
			"metadata": metadata,
			"line_items": StripeService._build_line_items(order),
		}
		if not request_payload["success_url"]:
			fallback_base = str(getattr(settings, "FRONTEND_PAYMENT_RESULT_URL", "") or "").strip()
			if not fallback_base:
				fallback_base = f"{settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'http://localhost:5173'}/payment-result"
			separator = "&" if "?" in fallback_base else "?"
			request_payload["success_url"] = f"{fallback_base}{separator}session_id={{CHECKOUT_SESSION_ID}}"
		try:
			session = stripe.checkout.Session.create(
				mode="payment",
				success_url=request_payload["success_url"],
				cancel_url=request_payload["cancel_url"],
				customer_email=order.customer_email,
				metadata=metadata,
				line_items=StripeService._build_line_items(order),
				idempotency_key=f"payment:{payment.reference}",
			)
		except stripe.error.StripeError as exc:
			logger.exception("Stripe checkout session creation failed for payment %s", payment.reference)
			raise serializers.ValidationError({"detail": [str(exc)]}) from exc

		if not getattr(session, "url", None):
			raise serializers.ValidationError({"detail": ["Unable to initialize Stripe checkout session."]})

		logger.info("Stripe checkout initialized for payment %s", payment.reference)
		return {
			"provider": Payment.Provider.STRIPE,
			"merchant_reference": str(order.merchant_reference),
			"redirect_url": str(session.url),
			"provider_reference": str(session.id),
			"provider_tracking_id": str(session.id),
			"status": Payment.Status.PENDING,
			"request_payload": request_payload,
			"response_payload": {
				"id": session.id,
				"url": session.url,
				"payment_status": getattr(session, "payment_status", None),
				"status": getattr(session, "status", None),
				"metadata": StripeService._coerce_mapping(getattr(session, "metadata", {}) or {}),
			},
		}

	@staticmethod
	def verify_payment(session_id: str) -> dict[str, Any]:
		"""Retrieve a Stripe Checkout Session server-side to verify its state."""
		stripe.api_key = StripeService._get_api_key()
		try:
			session = stripe.checkout.Session.retrieve(session_id)
		except stripe.error.StripeError as exc:
			logger.exception("Stripe session verification failed for %s", session_id)
			raise serializers.ValidationError({"detail": [str(exc)]}) from exc
		return {
			"id": session.id,
			"status": getattr(session, "status", None),
			"payment_status": getattr(session, "payment_status", None),
			"metadata": StripeService._coerce_mapping(getattr(session, "metadata", {}) or {}),
			"url": getattr(session, "url", None),
		}

	@staticmethod
	def _resolve_payment_from_event(event_data: dict[str, Any] | Any, *, payment: Payment | None = None) -> Payment | None:
		if payment is not None:
			return payment
		metadata = {}
		if isinstance(event_data, dict):
			metadata = dict(event_data.get("metadata") or {})
		else:
			metadata = dict(getattr(event_data, "metadata", {}) or {})
		payment_reference = metadata.get("payment_reference")
		order_reference = metadata.get("order_reference")
		provider_reference = metadata.get("provider_reference") or metadata.get("checkout_session_id")
		provider_tracking_id = metadata.get("provider_tracking_id")
		if payment_reference:
			try:
				return Payment.objects.select_related("order").get(reference=payment_reference)
			except Payment.DoesNotExist:
				pass
		if order_reference:
			return Payment.objects.select_related("order").filter(order__reference=order_reference).order_by("-created_at").first()
		if provider_reference:
			return Payment.objects.select_related("order").filter(provider_reference=provider_reference).order_by("-created_at").first()
		if provider_tracking_id:
			return Payment.objects.select_related("order").filter(provider_tracking_id=provider_tracking_id).order_by("-created_at").first()
		return None

	@staticmethod
	def _normalize_status_from_session(session_data: dict[str, Any]) -> str:
		payment_status = str(session_data.get("payment_status") or "").strip().lower()
		status = str(session_data.get("status") or "").strip().lower()
		if payment_status in {"paid", "succeeded", "complete", "complete"} or status in {"complete", "completed"}:
			return Payment.Status.COMPLETED
		if payment_status in {"unpaid", "open", "requires_payment_method", "requires_confirmation"}:
			return Payment.Status.PENDING
		if payment_status in {"no_payment_required"}:
			return Payment.Status.COMPLETED
		return Payment.Status.PENDING

	@staticmethod
	@transaction.atomic
	def handle_webhook(raw_body: bytes | str, *, headers: dict[str, str] | None = None, payment: Payment | None = None) -> Payment | None:
		"""Verify a Stripe webhook and update the associated payment/order if needed."""
		if not raw_body:
			raise serializers.ValidationError({"detail": ["Webhook payload is empty."]})

		headers = dict(headers or {})
		signature = headers.get("Stripe-Signature") or headers.get("stripe-signature")
		if not signature:
			raise serializers.ValidationError({"detail": ["Missing Stripe signature header."]})
		if not getattr(settings, "STRIPE_WEBHOOK_SECRET", ""):
			raise serializers.ValidationError({"detail": ["Stripe webhook secret is not configured."]})

		try:
			event = stripe.Webhook.construct_event(
				payload=raw_body,
				sig_header=signature,
				secret=settings.STRIPE_WEBHOOK_SECRET,
			)
		except (ValueError, stripe.error.SignatureVerificationError) as exc:
			raise serializers.ValidationError({"detail": ["Webhook signature is invalid."]}) from exc

		event_type = getattr(event, "type", None)
		if event_type not in StripeService.WEBHOOK_EVENTS:
			return None

		event_object = getattr(getattr(event, "data", None), "object", None) or {}
		metadata = dict(getattr(event_object, "metadata", {}) or {})
		provider_reference = metadata.get("provider_reference") or metadata.get("checkout_session_id")
		provider_tracking_id = metadata.get("provider_tracking_id")
		if not provider_reference and not provider_tracking_id:
			provider_reference = getattr(event_object, "id", None)
			provider_tracking_id = getattr(event_object, "id", None)

		resolved_payment = StripeService._resolve_payment_from_event(metadata, payment=payment)
		if resolved_payment is None and provider_reference:
			resolved_payment = Payment.objects.select_related("order").filter(provider_reference=provider_reference).order_by("-created_at").first()
		if resolved_payment is None and provider_tracking_id:
			resolved_payment = Payment.objects.select_related("order").filter(provider_tracking_id=provider_tracking_id).order_by("-created_at").first()
		if resolved_payment is None:
			raise serializers.ValidationError({"detail": ["Payment record not found for Stripe webhook."]})

		session_id = getattr(event_object, "id", None) or provider_reference or provider_tracking_id
		if session_id:
			verification_data = StripeService.verify_payment(session_id)
		else:
			verification_data = {"payment_status": "pending", "status": "open"}

		resolved_payment.provider_tracking_id = str(session_id or resolved_payment.provider_tracking_id or "")
		resolved_payment.checkout_response = dict(resolved_payment.checkout_response or {})
		webhook_events = resolved_payment.checkout_response.setdefault("webhook_events", [])
		if any(str(entry.get("id")) == str(event.id) for entry in webhook_events if isinstance(entry, dict)):
			return resolved_payment

		new_status = StripeService._normalize_status_from_session(verification_data)
		resolved_payment.status = new_status
		resolved_payment.checkout_response["webhook_payload"] = {
			"event_id": getattr(event, "id", None),
			"event_type": event_type,
			"data": dict(getattr(event, "data", {}) or {}),
		}
		webhook_events.append({"id": getattr(event, "id", None), "type": event_type, "status": new_status})
		resolved_payment.save(update_fields=["provider_tracking_id", "status", "checkout_response", "updated_at"])

		order = resolved_payment.order
		if new_status == Payment.Status.COMPLETED:
			order.status = Order.Status.PAID
		elif new_status == Payment.Status.FAILED:
			order.status = Order.Status.FAILED
		elif new_status == Payment.Status.CANCELLED:
			order.status = Order.Status.CANCELLED
		else:
			order.status = Order.Status.PENDING
		order.save(update_fields=["status", "updated_at"])
		return resolved_payment
