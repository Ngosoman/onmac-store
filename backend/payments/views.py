from django.db import DatabaseError
from rest_framework import generics, status
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
