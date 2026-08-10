import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import DatabaseError
from rest_framework import generics, status
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from .models import Order
from .serializers import OrderSerializer


logger = logging.getLogger(__name__)


class OrderError(APIException):
	status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
	default_detail = "Unable to process the order right now."
	default_code = "order_processing_error"


class OrderListCreateAPIView(generics.ListCreateAPIView):
	serializer_class = OrderSerializer
	queryset = Order.objects.prefetch_related("items").order_by("-created_at")

	@staticmethod
	def _send_order_notification(order: Order) -> None:
		recipient = str(getattr(settings, "ORDER_NOTIFICATION_EMAIL", "")).strip() or str(
			getattr(settings, "CONTACT_RECEIVER_EMAIL", "onmac.limited@gmail.com")
		).strip()
		if not recipient:
			return

		subject = f"[Onmac Order] {order.reference}"
		items = list(order.items.all())
		item_lines = [
			f"- {item.product_name} | qty: {item.quantity} | unit: {item.unit_price} | subtotal: {item.subtotal}"
			for item in items
		]
		if not item_lines:
			item_lines = ["- No order items available"]

		body = "\n".join(
			[
				"A new order was placed on Onmac Store.",
				"",
				f"Order reference: {order.reference}",
				f"Merchant reference: {order.merchant_reference or 'N/A'}",
				f"Status: {order.status}",
				f"Payment method: {order.payment_method or 'N/A'}",
				f"Currency: {order.currency}",
				f"Total amount: {order.total_amount}",
				"",
				f"Customer name: {order.customer_name}",
				f"Customer email: {order.customer_email}",
				f"Customer phone: {order.customer_phone or 'N/A'}",
				f"Shipping address: {order.shipping_address or 'N/A'}",
				"",
				"Items:",
				*item_lines,
			]
		)

		from_email = str(getattr(settings, "DEFAULT_FROM_EMAIL", recipient)).strip() or recipient
		email = EmailMessage(
			subject=subject,
			body=body,
			from_email=from_email,
			to=[recipient],
			reply_to=[order.customer_email],
		)
		email.send(fail_silently=False)

	def list(self, request, *args, **kwargs):
		response = super().list(request, *args, **kwargs)
		return Response({"orders": response.data}, status=response.status_code)

	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		order = None
		try:
			order = serializer.save()
			self._send_order_notification(order)
		except DatabaseError as exc:
			raise OrderError() from exc
		except Exception:
			logger.exception("Order email notification failed for order %s", getattr(order, "reference", "unknown"))

		output_serializer = self.get_serializer(order)
		headers = self.get_success_headers(output_serializer.data)
		return Response(output_serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class OrderDetailAPIView(generics.RetrieveAPIView):
	serializer_class = OrderSerializer
	lookup_field = "reference"
	lookup_url_kwarg = "reference"
	queryset = Order.objects.prefetch_related("items")
