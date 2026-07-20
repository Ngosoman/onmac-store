from django.db import DatabaseError
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

		if not order_tracking_id:
			raise exceptions.ValidationError({"OrderTrackingId": ["This field is required."]})

		return {
			"order_tracking_id": str(order_tracking_id),
			"merchant_reference": str(merchant_reference) if merchant_reference else None,
			"notification_type": str(notification_type) if notification_type else None,
		}

	def _reconcile(self, source_data):
		notification_data = self._extract_notification_data(source_data)
		payment = PaymentService.reconcile_pesapal_notification(**notification_data)
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
		return self._reconcile(request.query_params)


class PaymentIPNAPIView(_PesapalNotificationMixin, APIView):
	def get(self, request, *args, **kwargs):
		return self._reconcile(request.query_params)

	def post(self, request, *args, **kwargs):
		return self._reconcile(request.data)
