from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.db import transaction
from rest_framework import serializers

from orders.models import Order
from payments.models import Payment

logger = logging.getLogger(__name__)


class PayPalService:
    """PayPal Checkout integration adapter using Orders v2 REST API."""

    # PayPal REST API endpoints
    AUTH_ENDPOINT = "/v1/oauth2/token"
    CREATE_ORDER_ENDPOINT = "/v2/checkout/orders"
    CAPTURE_ORDER_ENDPOINT = "/v2/checkout/orders/{order_id}/capture"
    GET_ORDER_ENDPOINT = "/v2/checkout/orders/{order_id}"
    VERIFY_WEBHOOK_ENDPOINT = "/v1/notifications/verify-webhook-signature"

    REQUEST_TIMEOUT = (10, 30)

    # Mapping of PayPal order statuses to Payment statuses
    PAYPAL_TO_PAYMENT_STATUS = {
        "APPROVED": Payment.Status.PENDING,
        "COMPLETED": Payment.Status.COMPLETED,
        "VOIDED": Payment.Status.CANCELLED,
        "CREATED": Payment.Status.PENDING,
        "SAVED": Payment.Status.PENDING,
        "PAYER_ACTION_REQUIRED": Payment.Status.PENDING,
    }

    # Capture-level status mapping
    CAPTURE_STATUS_MAP = {
        "COMPLETED": Payment.Status.COMPLETED,
        "PARTIALLY_REFUNDED": Payment.Status.COMPLETED,
        "REFUNDED": Payment.Status.COMPLETED,
        "PENDING": Payment.Status.PENDING,
        "DECLINED": Payment.Status.FAILED,
        "FAILED": Payment.Status.FAILED,
    }

    # Only PAYMENT.CAPTURE.COMPLETED confirms actual fund settlement
    WEBHOOK_COMPLETION_EVENT = "PAYMENT.CAPTURE.COMPLETED"

    # Webhook event types we should inspect for order references
    WEBHOOK_EVENT_TYPES = {
        "PAYMENT.CAPTURE.COMPLETED",
        "CHECKOUT.ORDER.APPROVED",
        "CHECKOUT.ORDER.PROCESSED",
    }

    @staticmethod
    def _get_setting(name: str, *, required: bool = True, default: str = "") -> str:
        """Retrieve a Django setting with optional requirement check."""
        value = getattr(settings, name, default)
        if required and not value:
            raise serializers.ValidationError({"detail": [f"Missing required setting: {name}."]})
        return str(value)

    @staticmethod
    def _base_url() -> str:
        """Return the PayPal REST API base URL based on mode."""
        mode = PayPalService._get_setting("PAYPAL_MODE", required=False, default="sandbox").strip().lower()
        if mode == "live":
            return "https://api-m.paypal.com"
        return "https://api-m.sandbox.paypal.com"

    @staticmethod
    def _build_url(endpoint: str) -> str:
        """Build a full URL from the base and endpoint."""
        return f"{PayPalService._base_url()}{endpoint}"

    @staticmethod
    def _session(content_type: str = "application/json") -> requests.Session:
        """Create a configured requests session with the given Content-Type."""
        session = requests.Session()
        session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": content_type,
            }
        )
        return session

    @staticmethod
    def _authorization_header(token: str) -> dict[str, str]:
        """Build Bearer token authorization header."""
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _request(
        *,
        session: requests.Session,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
        data: str | None = None,
        error_context: str,
        auth: tuple[str, str] | None = None,
    ) -> dict[str, Any] | list[Any]:
        """
        Make an HTTP request with comprehensive error handling.

        Supports both JSON payload (via `payload`) and form-encoded body (via `data`).
        When `data` is provided, `payload` is ignored.
        """
        kwargs: dict[str, Any] = {
            "method": method,
            "url": url,
            "headers": headers,
            "timeout": PayPalService.REQUEST_TIMEOUT,
        }
        if auth:
            kwargs["auth"] = auth
        if data is not None:
            kwargs["data"] = data
        elif payload is not None:
            kwargs["json"] = payload

        try:
            response = session.request(**kwargs)
        except requests.Timeout as exc:
            logger.exception("PayPal request timed out during %s", error_context)
            raise serializers.ValidationError({"detail": ["Payment provider timeout. Please retry."]}) from exc
        except requests.ConnectionError as exc:
            logger.exception("PayPal connection error during %s", error_context)
            raise serializers.ValidationError({"detail": ["Payment provider is unreachable. Please retry."]}) from exc
        except requests.RequestException as exc:
            logger.exception("PayPal transport error during %s", error_context)
            raise serializers.ValidationError({"detail": ["Unable to contact payment provider right now."]}) from exc

        response_data: Any
        try:
            response_data = response.json()
        except ValueError as exc:
            logger.error(
                "PayPal returned non-JSON response during %s with status %s: %s",
                error_context,
                response.status_code,
                response.text[:500],
            )
            raise serializers.ValidationError({"detail": ["Unexpected response from payment provider."]}) from exc

        if response.status_code in (401, 403):
            logger.warning(
                "PayPal authorization failure during %s with status %s: %s",
                error_context,
                response.status_code,
                response_data,
            )
            raise serializers.ValidationError({"detail": ["Payment provider authentication failed."]})

        if response.status_code == 400:
            logger.warning("PayPal validation failure during %s: %s", error_context, response_data)
            message = PayPalService._safe_provider_message(response_data)
            raise serializers.ValidationError({"detail": [message]})

        if response.status_code >= 500:
            logger.error(
                "PayPal server failure during %s with status %s",
                error_context,
                response.status_code,
            )
            raise serializers.ValidationError({"detail": ["Payment provider is temporarily unavailable."]})

        if response.status_code >= 300:
            logger.error(
                "PayPal unexpected status %s during %s: %s",
                response.status_code,
                error_context,
                response_data,
            )
            raise serializers.ValidationError({"detail": ["Payment provider request failed."]})

        return response_data

    @staticmethod
    def _safe_provider_message(data: Any) -> str:
        """Extract a human-readable error message from a provider response."""
        if isinstance(data, dict):
            message = data.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
            details = data.get("details")
            if isinstance(details, list) and details:
                for detail in details:
                    if isinstance(detail, dict):
                        issue = detail.get("issue") or detail.get("description")
                        if issue:
                            return str(issue)
        return "Payment provider request failed."

    @staticmethod
    def authenticate(*, session: requests.Session | None = None) -> str:
        """
        Authenticate against PayPal OAuth2 and return an access token.

        Uses the client_credentials grant type with Basic Auth.
        Sends form-encoded body as required by PayPal's OAuth2 endpoint.
        """
        client_id = PayPalService._get_setting("PAYPAL_CLIENT_ID")
        client_secret = PayPalService._get_setting("PAYPAL_CLIENT_SECRET")

        # PayPal OAuth2 requires application/x-www-form-urlencoded
        auth_session = PayPalService._session(content_type="application/x-www-form-urlencoded")
        auth = (client_id, client_secret)

        # Form-encoded body per PayPal REST API spec
        form_data = urlencode({"grant_type": "client_credentials"})

        logger.info("Authenticating with PayPal OAuth2")

        response_data = PayPalService._request(
            session=auth_session,
            method="POST",
            url=PayPalService._build_url(PayPalService.AUTH_ENDPOINT),
            data=form_data,
            auth=auth,
            error_context="authenticate",
        )

        if not isinstance(response_data, dict):
            raise serializers.ValidationError({"detail": ["Invalid authentication response from payment provider."]})

        token = response_data.get("access_token")
        if not token:
            logger.error("PayPal OAuth2 response missing access_token")
            raise serializers.ValidationError({"detail": ["Failed to authenticate payment provider."]})

        logger.info("PayPal OAuth2 authentication successful")
        return str(token)

    @staticmethod
    def _build_order_payload(order: Order, payment: Payment) -> dict[str, Any]:
        """Build the PayPal order creation request payload."""
        currency = str(order.currency).upper()
        total = str(Decimal(order.total_amount).quantize(Decimal("0.01")))

        purchase_unit: dict[str, Any] = {
            "reference_id": str(payment.reference),
            "description": f"Order {order.reference} payment",
            "amount": {
                "currency_code": currency,
                "value": total,
            },
            "custom_id": str(order.reference),
            "invoice_id": str(payment.reference),
        }

        # Add items if available
        items_data = []
        for item in order.items.all():
            item_unit_price = str(Decimal(item.unit_price).quantize(Decimal("0.01")))
            items_data.append({
                "name": str(item.product_name)[:127],
                "quantity": str(item.quantity),
                "unit_amount": {
                    "currency_code": currency,
                    "value": item_unit_price,
                },
                "category": "PHYSICAL_GOODS",
            })

        if items_data:
            purchase_unit["items"] = items_data
            purchase_unit["amount"]["breakdown"] = {
                "item_total": {
                    "currency_code": currency,
                    "value": total,
                },
            }

        application_context = {
            "brand_name": "Beast Store",
            "landing_page": "NO_PREFERENCE",
            "user_action": "PAY_NOW",
            "return_url": PayPalService._get_setting("PAYPAL_RETURN_URL", required=False, default=""),
            "cancel_url": PayPalService._get_setting("PAYPAL_CANCEL_URL", required=False, default=""),
        }

        request_payload: dict[str, Any] = {
            "intent": "CAPTURE",
            "purchase_units": [purchase_unit],
            "payment_source": {
                "paypal": {
                    "experience_context": application_context,
                }
            },
        }

        return request_payload

    @staticmethod
    def _extract_approval_url(order_data: dict[str, Any]) -> str:
        """Extract the approval URL from the PayPal order response."""
        links = order_data.get("links", [])
        for link in links:
            if isinstance(link, dict) and link.get("rel") in ("payer-action", "approve"):
                href = link.get("href")
                if href:
                    return str(href)
        return ""

    @staticmethod
    def _normalize_status(provider_status: str | None) -> str:
        """Map PayPal order status to Payment status."""
        if not provider_status:
            return Payment.Status.PENDING
        return PayPalService.PAYPAL_TO_PAYMENT_STATUS.get(
            str(provider_status).strip().upper(),
            Payment.Status.PENDING,
        )

    @staticmethod
    def _inspect_capture_status(capture_response: dict[str, Any]) -> str:
        """
        Inspect the capture response and determine the actual payment status.

        Examines the purchase_units -> captures[].status to determine
        the real PayPal settlement state. Only returns COMPLETED if
        at least one capture completed successfully.
        """
        # Check the top-level order status first
        order_status = capture_response.get("status", "").strip().upper()

        # Look at all purchase units captures
        purchase_units = capture_response.get("purchase_units", [])
        if not purchase_units:
            logger.warning("No purchase_units in capture response, using order status: %s", order_status)
            return PayPalService._normalize_status(order_status)

        capture_statuses = []
        for unit in purchase_units:
            if not isinstance(unit, dict):
                continue
            payments_data = unit.get("payments", {})
            if not isinstance(payments_data, dict):
                continue
            captures = payments_data.get("captures", [])
            if not isinstance(captures, list):
                continue
            for capture in captures:
                if not isinstance(capture, dict):
                    continue
                cap_status = capture.get("status", "").strip().upper()
                cap_id = capture.get("id", "unknown")
                logger.info(
                    "Capture %s has status %s for purchase unit %s",
                    cap_id,
                    cap_status,
                    unit.get("reference_id", "unknown"),
                )
                capture_statuses.append(cap_status)

        if not capture_statuses:
            logger.warning("No captures found in response, using order status: %s", order_status)
            return PayPalService._normalize_status(order_status)

        # If any capture completed, the payment is successful
        # If all captures failed, payment failed
        # Otherwise keep pending
        all_completed = all(s == "COMPLETED" for s in capture_statuses)
        any_completed = any(s == "COMPLETED" for s in capture_statuses)
        any_failed = any(s in ("FAILED", "DECLINED") for s in capture_statuses)

        if all_completed or any_completed:
            logger.info("Capture successful: %s", capture_statuses)
            return Payment.Status.COMPLETED
        if any_failed:
            logger.warning("Capture failed: %s", capture_statuses)
            return Payment.Status.FAILED

        logger.info("Capture pending: %s", capture_statuses)
        return Payment.Status.PENDING

    @staticmethod
    def create_payment(order: Order, payment: Payment) -> dict[str, Any]:
        """
        Create a PayPal Order via Orders v2 REST API.

        Returns normalized payment details including the approval URL
        for redirecting the customer.
        """
        session = PayPalService._session()
        token = PayPalService.authenticate(session=session)

        request_payload = PayPalService._build_order_payload(order, payment)

        logger.info(
            "Creating PayPal order for payment %s and order %s",
            payment.reference,
            order.reference,
        )

        response_data = PayPalService._request(
            session=session,
            method="POST",
            url=PayPalService._build_url(PayPalService.CREATE_ORDER_ENDPOINT),
            headers=PayPalService._authorization_header(token),
            payload=request_payload,
            error_context="create_order",
        )

        if not isinstance(response_data, dict):
            raise serializers.ValidationError({"detail": ["Invalid checkout response from payment provider."]})

        paypal_order_id = response_data.get("id")
        provider_status = response_data.get("status")
        approval_url = PayPalService._extract_approval_url(response_data)

        if not paypal_order_id:
            logger.error(
                "PayPal create order response missing order ID for payment %s",
                payment.reference,
            )
            raise serializers.ValidationError({"detail": ["Unable to initialize checkout session."]})

        normalized_status = PayPalService._normalize_status(provider_status)

        logger.info(
            "PayPal order %s created for payment %s with status %s",
            paypal_order_id,
            payment.reference,
            normalized_status,
        )

        return {
            "provider": Payment.Provider.PAYPAL,
            "merchant_reference": str(order.reference),
            "redirect_url": approval_url,
            "provider_reference": paypal_order_id,
            "provider_tracking_id": paypal_order_id,
            "status": normalized_status,
            "request_payload": request_payload,
            "response_payload": response_data,
        }

    @staticmethod
    def capture_payment(order_id: str) -> dict[str, Any]:
        """
        Capture an approved PayPal order.

        Called after the customer approves the payment on PayPal's site.
        Returns the full capture response for status inspection.
        """
        session = PayPalService._session()
        token = PayPalService.authenticate(session=session)

        url = PayPalService._build_url(
            PayPalService.CAPTURE_ORDER_ENDPOINT.format(order_id=order_id)
        )

        logger.info("Capturing PayPal order %s", order_id)

        response_data = PayPalService._request(
            session=session,
            method="POST",
            url=url,
            headers=PayPalService._authorization_header(token),
            error_context="capture_order",
        )

        if not isinstance(response_data, dict):
            raise serializers.ValidationError({"detail": ["Invalid capture response from payment provider."]})

        logger.info("PayPal order %s captured, inspecting status", order_id)
        return response_data

    @staticmethod
    def verify_payment(order_id: str) -> dict[str, Any]:
        """
        Get the current status of a PayPal order.

        Used to verify payment status after capture or from webhook callbacks.
        """
        session = PayPalService._session()
        token = PayPalService.authenticate(session=session)

        url = PayPalService._build_url(
            PayPalService.GET_ORDER_ENDPOINT.format(order_id=order_id)
        )

        logger.info("Verifying PayPal order %s", order_id)

        response_data = PayPalService._request(
            session=session,
            method="GET",
            url=url,
            headers=PayPalService._authorization_header(token),
            error_context="get_order",
        )

        if not isinstance(response_data, dict):
            raise serializers.ValidationError({"detail": ["Invalid order status response from payment provider."]})

        return response_data

    @staticmethod
    @transaction.atomic
    def handle_capture(order_id: str) -> Payment:
        """
        Process the capture of a PayPal order after customer approval.

        - Captures the PayPal order server-side (never trust frontend)
        - Inspects the actual PayPal capture response for real status
        - Updates Payment.status accordingly (COMPLETED only if PayPal confirms)
        - Updates Order.status accordingly
        - Returns the updated Payment
        """
        try:
            payment = Payment.objects.select_related("order").get(
                provider_reference=order_id,
                provider=Payment.Provider.PAYPAL,
            )
        except Payment.DoesNotExist:
            logger.error("PayPal payment not found for order ID %s", order_id)
            raise serializers.ValidationError({"detail": ["Payment record not found for PayPal order."]})

        # Capture the PayPal order server-side (never trust the frontend)
        capture_response = PayPalService.capture_payment(order_id)

        # Determine actual payment status from PayPal's response
        payment_status = PayPalService._inspect_capture_status(capture_response)

        # Update payment record with real status from PayPal
        payment.provider_tracking_id = order_id
        payment.status = payment_status
        payment.checkout_response = dict(payment.checkout_response or {})
        payment.checkout_response["capture_response"] = capture_response
        payment.save(
            update_fields=[
                "provider_tracking_id",
                "status",
                "checkout_response",
                "updated_at",
            ]
        )

        # Update order status to match payment
        order = payment.order
        if payment_status == Payment.Status.COMPLETED:
            order.status = Order.Status.PAID
        elif payment_status == Payment.Status.FAILED:
            order.status = Order.Status.FAILED
        else:
            order.status = Order.Status.PENDING
        order.save(update_fields=["status", "updated_at"])

        logger.info(
            "Payment %s for order %s processed via PayPal capture → status=%s",
            payment.reference,
            order.reference,
            payment_status,
        )

        return payment

    @staticmethod
    def _verify_webhook_signature(
        *,
        headers: dict[str, str],
        body: str,
    ) -> bool:
        """Verify that a webhook notification came from PayPal."""
        webhook_id = PayPalService._get_setting("PAYPAL_WEBHOOK_ID", required=False, default="")
        if not webhook_id:
            logger.warning("PAYPAL_WEBHOOK_ID not configured; skipping webhook signature verification")
            return True

        session = PayPalService._session()
        token = PayPalService.authenticate(session=session)

        transmission_id = headers.get("paypal-transmission-id", "")
        transmission_time = headers.get("paypal-transmission-time", "")
        cert_url = headers.get("paypal-cert-url", "")
        auth_algo = headers.get("paypal-auth-algo", "")
        transmission_sig = headers.get("paypal-transmission-sig", "")

        verify_payload = {
            "auth_algo": auth_algo,
            "cert_url": cert_url,
            "transmission_id": transmission_id,
            "transmission_sig": transmission_sig,
            "transmission_time": transmission_time,
            "webhook_id": webhook_id,
            "webhook_event": json.loads(body) if isinstance(body, str) else body,
        }

        try:
            response_data = PayPalService._request(
                session=session,
                method="POST",
                url=PayPalService._build_url(PayPalService.VERIFY_WEBHOOK_ENDPOINT),
                headers=PayPalService._authorization_header(token),
                payload=verify_payload,
                error_context="verify_webhook",
            )
        except serializers.ValidationError:
            logger.exception("PayPal webhook signature verification request failed")
            return False

        if isinstance(response_data, dict):
            verification_status = response_data.get("verification_status")
            return verification_status == "SUCCESS"

        return False

    @staticmethod
    @transaction.atomic
    def handle_webhook(
        payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
        body: str | None = None,
    ) -> Payment | None:
        """
        Handle an incoming PayPal webhook event.

        - Verifies webhook signature
        - Only processes PAYMENT.CAPTURE.COMPLETED for payment completion
        - Ignores CHECKOUT.ORDER.APPROVED (customer approval != payment)
        - Idempotent: skips if payment already COMPLETED
        """
        if not isinstance(payload, dict):
            raise serializers.ValidationError({"detail": ["Invalid webhook payload."]})

        # Verify webhook signature when configured
        if headers and body:
            if not PayPalService._verify_webhook_signature(headers=headers, body=body):
                logger.warning("PayPal webhook signature verification failed")
                raise serializers.ValidationError({"detail": ["Webhook signature is invalid."]})

        event_type = payload.get("event_type", "")

        # Only process known event types
        if event_type not in PayPalService.WEBHOOK_EVENT_TYPES:
            logger.info("Ignoring PayPal webhook event type: %s", event_type)
            return None

        resource = payload.get("resource", {})
        if not isinstance(resource, dict):
            logger.warning("PayPal webhook resource is not a dict")
            return None

        # Extract the PayPal order ID from the webhook resource
        paypal_order_id = None

        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            # For capture completion, get order_id from supplementary_data
            supplementary_data = resource.get("supplementary_data", {})
            if isinstance(supplementary_data, dict):
                related_ids = supplementary_data.get("related_ids", {})
                if isinstance(related_ids, dict):
                    paypal_order_id = related_ids.get("order_id")
            # Fallback: custom_id on the capture resource
            if not paypal_order_id:
                custom_id = resource.get("custom_id", "")
                if custom_id:
                    # custom_id is the order reference, look up via payment
                    try:
                        payment = Payment.objects.select_related("order").filter(
                            order__reference=custom_id,
                            provider=Payment.Provider.PAYPAL,
                        ).order_by("-created_at").first()
                        if payment:
                            paypal_order_id = payment.provider_reference
                    except Payment.DoesNotExist:
                        pass
        else:
            # For order-level events, resource.id is the order ID
            paypal_order_id = resource.get("id")

        if not paypal_order_id:
            logger.warning("Could not extract PayPal order ID from webhook payload")
            return None

        # Find the payment record
        try:
            payment = Payment.objects.select_related("order").get(
                provider_reference=paypal_order_id,
                provider=Payment.Provider.PAYPAL,
            )
        except Payment.DoesNotExist:
            logger.error("PayPal payment not found for order ID %s from webhook", paypal_order_id)
            return None

        # Store webhook event for audit trail
        payment.checkout_response = dict(payment.checkout_response or {})
        payment.checkout_response.setdefault("webhook_events", [])
        payment.checkout_response["webhook_events"].append({
            "event_type": event_type,
            "event_id": payload.get("id"),
            "create_time": payload.get("create_time"),
            "resource_id": resource.get("id"),
            "summary": payload.get("summary", ""),
        })

        # Only PAYMENT.CAPTURE.COMPLETED confirms actual fund settlement
        # CHECKOUT.ORDER.APPROVED means customer approved, NOT that funds settled
        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            # Idempotent: skip if already completed
            if payment.status == Payment.Status.COMPLETED:
                logger.info(
                    "Payment %s already completed; skipping duplicate webhook %s",
                    payment.reference,
                    event_type,
                )
                payment.save(update_fields=["checkout_response", "updated_at"])
                return payment

            # Mark as completed
            payment.status = Payment.Status.COMPLETED
            payment.save(update_fields=["status", "checkout_response", "updated_at"])

            order = payment.order
            order.status = Order.Status.PAID
            order.save(update_fields=["status", "updated_at"])

            logger.info(
                "Payment %s for order %s completed via PayPal webhook %s",
                payment.reference,
                order.reference,
                event_type,
            )
        elif event_type == "CHECKOUT.ORDER.APPROVED":
            # Customer approved but payment not yet captured.
            # We do NOT mark the order paid here — capture will happen
            # via return URL callback.
            logger.info(
                "PayPal order %s approved by customer (payment %s). Awaiting capture.",
                paypal_order_id,
                payment.reference,
            )
            payment.save(update_fields=["checkout_response", "updated_at"])
        else:
            # For other events, just save the audit trail
            payment.save(update_fields=["checkout_response", "updated_at"])

        return payment

