from django.db import DatabaseError
from rest_framework import generics, status
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from .models import Order
from .serializers import OrderSerializer


class OrderError(APIException):
	status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
	default_detail = "Unable to process the order right now."
	default_code = "order_processing_error"


class OrderListCreateAPIView(generics.ListCreateAPIView):
	serializer_class = OrderSerializer
	queryset = Order.objects.prefetch_related("items").order_by("-created_at")

	def list(self, request, *args, **kwargs):
		response = super().list(request, *args, **kwargs)
		return Response({"orders": response.data}, status=response.status_code)

	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		try:
			order = serializer.save()
		except DatabaseError as exc:
			raise OrderError() from exc

		output_serializer = self.get_serializer(order)
		headers = self.get_success_headers(output_serializer.data)
		return Response(output_serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class OrderDetailAPIView(generics.RetrieveAPIView):
	serializer_class = OrderSerializer
	lookup_field = "reference"
	lookup_url_kwarg = "reference"
	queryset = Order.objects.prefetch_related("items")
