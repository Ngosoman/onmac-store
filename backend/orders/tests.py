from decimal import Decimal

from django.test import TestCase
from rest_framework import serializers

from .models import Order
from .serializers import OrderSerializer
from .services import OrderService


class OrderSerializerTests(TestCase):
	def _item_payload(self, **overrides):
		payload = {
			"product_id": 101,
			"product_name": "Test Product",
			"quantity": 2,
			"unit_price": "150.00",
		}
		payload.update(overrides)
		return payload

	def _order_payload(self, **overrides):
		payload = {
			"customer_name": "Jane Doe",
			"customer_email": "jane@example.com",
			"customer_phone": "+254700000000",
			"shipping_address": "Nairobi",
			"payment_method": "PESAPAL",
			"currency": "KES",
			"items": [self._item_payload()],
		}
		payload.update(overrides)
		return payload

	def test_items_are_required_and_cannot_be_empty(self):
		serializer = OrderSerializer(data=self._order_payload(items=[]))

		self.assertFalse(serializer.is_valid())
		self.assertIn("items", serializer.errors)

	def test_payment_method_must_match_allowed_choices(self):
		serializer = OrderSerializer(data=self._order_payload(payment_method="CASH"))

		self.assertFalse(serializer.is_valid())
		self.assertIn("payment_method", serializer.errors)

	def test_read_only_order_fields_are_ignored_from_input(self):
		serializer = OrderSerializer(
			data=self._order_payload(
				reference="00000000-0000-0000-0000-000000000000",
				merchant_reference="MR-CLIENT",
				pesapal_tracking_id="TRACK-123",
				total_amount="9999.99",
			)
		)

		self.assertTrue(serializer.is_valid(), serializer.errors)
		self.assertNotIn("reference", serializer.validated_data)
		self.assertNotIn("merchant_reference", serializer.validated_data)
		self.assertNotIn("pesapal_tracking_id", serializer.validated_data)
		self.assertNotIn("total_amount", serializer.validated_data)

	def test_paid_orders_cannot_be_modified_through_serializer(self):
		order = Order.objects.create(
			customer_name="Jane Doe",
			customer_email="jane@example.com",
			status=Order.Status.PAID,
		)
		serializer = OrderSerializer(order, data={"customer_name": "Changed"}, partial=True)

		self.assertFalse(serializer.is_valid())
		self.assertEqual(serializer.errors["status"][0], "Paid orders cannot be modified.")


class OrderServiceTests(TestCase):
	def _validated_order_data(self):
		return {
			"customer_name": "Jane Doe",
			"customer_email": "jane@example.com",
			"customer_phone": "+254700000000",
			"shipping_address": "Nairobi",
			"payment_method": "PESAPAL",
			"currency": "KES",
			"items": [
				{
					"product_id": 101,
					"product_name": "Test Product",
					"quantity": 2,
					"unit_price": Decimal("150.00"),
				},
				{
					"product_id": 102,
					"product_name": "Second Product",
					"quantity": 1,
					"unit_price": Decimal("50.00"),
				},
			],
		}

	def test_create_order_calculates_totals_from_order_items(self):
		order = OrderService.create_order(self._validated_order_data())

		order.refresh_from_db()
		self.assertEqual(order.total_amount, Decimal("350.00"))
		self.assertEqual(order.items.count(), 2)
		self.assertEqual(order.items.first().subtotal, Decimal("300.00"))

	def test_update_order_rejects_paid_orders(self):
		order = Order.objects.create(
			customer_name="Jane Doe",
			customer_email="jane@example.com",
			status=Order.Status.PAID,
		)

		with self.assertRaises(serializers.ValidationError):
			OrderService.update_order(order, {"customer_name": "Changed"})
