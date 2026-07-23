from django.db import DatabaseError
from django.conf import settings
from django.shortcuts import redirect
from urllib.parse import urlencode
from rest_framework import exceptions
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from .models import Payment
from .serializers import PaymentInitiationSerializer, PaymentSerializer
from .services import PaymentService


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
