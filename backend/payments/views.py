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

from .models import Payment
from .serializers import PaymentInitiationSerializer, PaymentSerializer
from .services import PaymentService
from .paypal_service import PayPalService


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
