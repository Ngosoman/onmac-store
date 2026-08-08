import json
import logging

from django.db import DatabaseError
from django.conf import settings
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from urllib.parse import urlencode
from rest_framework import exceptions, serializers
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from orders.models import Order

from .models import Payment
from .serializers import PaymentInitiationSerializer, PaymentSerializer
from .services import PaymentService
from .paypal_service import PayPalService
from .stripe_service import StripeService


logger = logging.getLogger(__name__)


class PaymentError(APIException):
	status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
	default_detail = "Unable to process the payment right now."
	default_code = "payment_processing_error"


class PaymentInitiationAPIView(generics.GenericAPIView):
	serializer_class = PaymentInitiationSerializer

	def post(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		try:
			payment = PaymentService.initiate_payment(**serializer.validated_data)
		except serializers.ValidationError as exc:
			return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
		except DatabaseError as exc:
			raise PaymentError() from exc

		output_serializer = PaymentSerializer(payment)
		return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class PaymentDetailAPIView(generics.RetrieveAPIView):
	serializer_class = PaymentSerializer
	lookup_field = "reference"
	lookup_url_kwarg = "reference"
	queryset = Payment.objects.select_related("order")


class OrderPaymentListAPIView(generics.ListAPIView):
	serializer_class = PaymentSerializer

	def get_queryset(self):
		order_reference = self.kwargs["order_reference"]
		return Payment.objects.select_related("order").filter(order__reference=order_reference).order_by("-created_at")


class _PesapalNotificationMixin:
	@staticmethod
	def _extract_notification_data(source_data):
		order_tracking_id = source_data.get("OrderTrackingId") or source_data.get("order_tracking_id")
		merchant_reference = source_data.get("OrderMerchantReference") or source_data.get("order_merchant_reference")
		notification_type = source_data.get("OrderNotificationType") or source_data.get("order_notification_type")

		if not order_tracking_id and not (source_data.get("payment_id") or source_data.get("id") or source_data.get("invoice_id")):
			return {
				"order_tracking_id": None,
				"merchant_reference": str(merchant_reference) if merchant_reference else None,
				"notification_type": str(notification_type) if notification_type else None,
			}

		return {
			"order_tracking_id": str(order_tracking_id) if order_tracking_id else None,
			"merchant_reference": str(merchant_reference) if merchant_reference else None,
			"notification_type": str(notification_type) if notification_type else None,
		}

	def _reconcile(self, source_data):
		notification_data = self._extract_notification_data(source_data)
		payload = dict(source_data)
		payment = PaymentService.reconcile_notification(payload=payload, headers=dict(getattr(self.request, "headers", {}) or {}))
		return Response(
			{
				"message": "Payment notification processed.",
				"payment_reference": str(payment.reference),
				"payment_status": payment.status,
				"order_reference": str(payment.order.reference),
				"order_status": payment.order.status,
			},
			status=status.HTTP_200_OK,
		)


class PaymentCallbackAPIView(_PesapalNotificationMixin, APIView):
	def get(self, request, *args, **kwargs):
		notification_data = self._extract_notification_data(request.query_params)
		payment = PaymentService.reconcile_notification(payload=dict(request.query_params), headers=dict(request.headers))

		result_url = str(getattr(settings, "FRONTEND_PAYMENT_RESULT_URL", "")).strip()
		if not result_url:
			return Response(
				{
					"message": "Payment callback processed.",
					"payment_reference": str(payment.reference),
					"payment_status": payment.status,
					"order_reference": str(payment.order.reference),
					"order_status": payment.order.status,
				},
				status=status.HTTP_200_OK,
			)

		query = urlencode(
			{
				"payment_reference": str(payment.reference),
				"payment_status": payment.status,
				"order_reference": str(payment.order.reference),
				"order_status": payment.order.status,
				"order_tracking_id": notification_data["order_tracking_id"],
			}
		)
		separator = "&" if "?" in result_url else "?"
		return redirect(f"{result_url}{separator}{query}")


class PaymentIPNAPIView(_PesapalNotificationMixin, APIView):
	def get(self, request, *args, **kwargs):
		return self._reconcile(request.query_params)

	def post(self, request, *args, **kwargs):
		return self._reconcile(request.data)


class StripeSuccessAPIView(APIView):
	def get(self, request, *args, **kwargs):
		session_id = request.query_params.get("session_id") or request.query_params.get("session")
		no_redirect = str(request.query_params.get("no_redirect") or "").strip().lower() in {"1", "true", "yes"}
		if not session_id:
			return Response({"detail": ["Missing Stripe session identifier."]}, status=status.HTTP_400_BAD_REQUEST)

		try:
			verification = StripeService.verify_payment(session_id)
		except serializers.ValidationError as exc:
			return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

		payment = None
		metadata = verification.get("metadata") or {}
		payment_reference = metadata.get("payment_reference") if isinstance(metadata, dict) else None
		order_reference = metadata.get("order_reference") if isinstance(metadata, dict) else None
		if payment_reference:
			try:
				payment = Payment.objects.select_related("order").get(reference=payment_reference)
			except Payment.DoesNotExist:
				payment = None
		if payment is None and order_reference:
			payment = Payment.objects.select_related("order").filter(order__reference=order_reference).order_by("-created_at").first()
		if payment is None:
			payment = Payment.objects.select_related("order").filter(provider_reference=session_id).order_by("-created_at").first()
		if payment is None:
			payment = Payment.objects.select_related("order").filter(provider_tracking_id=session_id).order_by("-created_at").first()

		provider_payment_status = str(verification.get("payment_status") or "").strip().lower()
		is_paid = provider_payment_status in {"paid", "succeeded", "complete"}
		resolved_payment_status = Payment.Status.COMPLETED if is_paid else Payment.Status.PENDING
		resolved_order_status = Order.Status.PAID if is_paid else Order.Status.PENDING

		if payment is not None and is_paid:
			payment.status = Payment.Status.COMPLETED
			payment.save(update_fields=["status", "updated_at"])
			payment.order.status = Order.Status.PAID
			payment.order.save(update_fields=["status", "updated_at"])
			resolved_payment_status = payment.status
			resolved_order_status = payment.order.status
		elif payment is not None:
			resolved_payment_status = payment.status
			resolved_order_status = payment.order.status

		resolved_payment_reference = str(payment.reference) if payment is not None else str(payment_reference or session_id)
		resolved_order_reference = str(payment.order.reference) if payment is not None else str(order_reference or "")

		result_url = str(getattr(settings, "FRONTEND_PAYMENT_RESULT_URL", "")).strip()
		if result_url and not no_redirect:
			query = urlencode({
				"payment_reference": resolved_payment_reference,
				"payment_status": resolved_payment_status,
				"order_reference": resolved_order_reference,
				"order_status": resolved_order_status,
				"order_tracking_id": str(session_id),
			})
			separator = "&" if "?" in result_url else "?"
			return redirect(f"{result_url}{separator}{query}")

		return Response({
			"message": "Stripe payment verified.",
			"payment_reference": resolved_payment_reference,
			"payment_status": resolved_payment_status,
			"order_reference": resolved_order_reference,
			"order_status": resolved_order_status,
			"order_tracking_id": str(session_id),
			"provider_payment_status": provider_payment_status,
		}, status=status.HTTP_200_OK)


class PayPalCaptureAPIView(APIView):
	"""
	Capture a PayPal order after the customer has approved it.

	Receives the PayPal Order ID from the frontend (returned via redirect
	after customer approval on PayPal's site).
	"""

	def get(self, request, *args, **kwargs):
		"""
		Handle GET callback from PayPal redirect after customer approval.

		PayPal redirects back with `token` (the Order ID) in query params.
		"""
		paypal_order_id = request.query_params.get("token")
		if not paypal_order_id:
			return Response(
				{"detail": ["Missing PayPal order token."]},
				status=status.HTTP_400_BAD_REQUEST,
			)

		try:
			payment = PayPalService.handle_capture(paypal_order_id)
		except serializers.ValidationError as exc:
			return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

		result_url = str(getattr(settings, "FRONTEND_PAYMENT_RESULT_URL", "")).strip()
		if result_url:
			query = urlencode({
				"payment_reference": str(payment.reference),
				"payment_status": payment.status,
				"order_reference": str(payment.order.reference),
				"order_status": payment.order.status,
			})
			separator = "&" if "?" in result_url else "?"
			return redirect(f"{result_url}{separator}{query}")

		return Response(
			{
				"message": "PayPal payment captured successfully.",
				"payment_reference": str(payment.reference),
				"payment_status": payment.status,
				"order_reference": str(payment.order.reference),
				"order_status": payment.order.status,
			},
			status=status.HTTP_200_OK,
		)

	def post(self, request, *args, **kwargs):
		"""
		Handle POST capture request from the frontend.

		The frontend sends the PayPal Order ID after customer approval.
		This is the server-side capture that never trusts the frontend.
		"""
		paypal_order_id = request.data.get("order_id") or request.data.get("token")
		if not paypal_order_id:
			return Response(
				{"detail": ["Missing PayPal order ID."]},
				status=status.HTTP_400_BAD_REQUEST,
			)

		try:
			payment = PayPalService.handle_capture(paypal_order_id)
		except serializers.ValidationError as exc:
			return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

		return Response(
			{
				"message": "PayPal payment captured successfully.",
				"payment_reference": str(payment.reference),
				"payment_status": payment.status,
				"order_reference": str(payment.order.reference),
				"order_status": payment.order.status,
			},
			status=status.HTTP_200_OK,
		)


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookAPIView(APIView):
	authentication_classes = []
	permission_classes = []

	def post(self, request, *args, **kwargs):
		body = request.body
		try:
			payment = StripeService.handle_webhook(body, headers=dict(request.headers))
		except serializers.ValidationError as exc:
			logger.warning("Stripe webhook rejected: %s", exc.detail)
			return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

		if payment:
			logger.info("Stripe webhook processed for payment %s", payment.reference)
		else:
			logger.info("Stripe webhook ignored")
		return Response({"status": "received"}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class PayPalWebhookAPIView(APIView):
	"""
	Handle incoming PayPal webhook events.

	Verifies the webhook signature and processes completion events
	to update Payment and Order status.
	"""

	authentication_classes = []
	permission_classes = []

	def post(self, request, *args, **kwargs):
		raw_body = request.body.decode("utf-8") if request.body else ""
		headers = dict(request.headers)

		try:
			payload = json.loads(raw_body) if raw_body else {}
		except json.JSONDecodeError:
			return Response(
				{"detail": ["Invalid JSON payload."]},
				status=status.HTTP_400_BAD_REQUEST,
			)

		try:
			payment = PayPalService.handle_webhook(
				payload,
				headers=headers,
				body=raw_body,
			)
		except serializers.ValidationError as exc:
			logger.warning("PayPal webhook rejected: %s", exc.detail)
			return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

		if payment:
			logger.info(
				"PayPal webhook %s processed for payment %s",
				payload.get("event_type", "unknown"),
				payment.reference,
			)
		else:
			logger.info("PayPal webhook event %s ignored", payload.get("event_type", "unknown"))

		return Response({"status": "received"}, status=status.HTTP_200_OK)
