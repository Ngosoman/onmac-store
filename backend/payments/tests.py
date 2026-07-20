from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework import serializers
from rest_framework.test import APIClient

from orders.models import Order, OrderItem

from .models import Payment
from .services import PaymentService


class PaymentServiceTests(TestCase):
	def setUp(self):
		self.order = Order.objects.create(
			customer_name="Jane Doe",
			customer_email="jane@example.com",
			payment_method="PESAPAL",
			currency="KES",
			total_amount=Decimal("350.00"),
		)
		OrderItem.objects.create(
			order=self.order,
			product_id=101,
			product_name="Test Product",
			quantity=2,
			unit_price=Decimal("175.00"),
			subtotal=Decimal("350.00"),
		)

	def test_initiate_payment_uses_order_totals_and_creates_pending_payment(self):
		with patch("payments.services.PesapalService.create_payment") as mock_create_payment:
			mock_create_payment.return_value = {
				"provider": Payment.Provider.PESAPAL,
				"merchant_reference": self.order.merchant_reference,
				"redirect_url": "https://cybqa.pesapal.com/pesapaliframe/checkout/abc",
				"provider_reference": self.order.merchant_reference,
				"provider_tracking_id": "b945e4af-80a5-4ec1-8706-e03f8332fb04",
				"status": Payment.Status.PENDING,
				"request_payload": {"id": self.order.merchant_reference},
				"response_payload": {"status": "200"},
			}
			payment = PaymentService.initiate_payment(
				order_reference=str(self.order.reference),
				provider=Payment.Provider.PESAPAL,
			)

		self.assertEqual(payment.amount, Decimal("350.00"))
		self.assertEqual(payment.currency, "KES")
		self.assertEqual(payment.status, Payment.Status.PENDING)
		self.assertTrue(payment.redirect_url)

	def test_initiate_payment_rejects_paid_orders(self):
		self.order.status = Order.Status.PAID
		self.order.save(update_fields=["status"])

		with self.assertRaises(serializers.ValidationError):
			PaymentService.initiate_payment(
				order_reference=str(self.order.reference),
				provider=Payment.Provider.PESAPAL,
			)


class PaymentApiTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.order = Order.objects.create(
			customer_name="Jane Doe",
			customer_email="jane@example.com",
			currency="KES",
			total_amount=Decimal("120.00"),
		)
		OrderItem.objects.create(
			order=self.order,
			product_id=201,
			product_name="API Product",
			quantity=1,
			unit_price=Decimal("120.00"),
			subtotal=Decimal("120.00"),
		)

	def test_post_initiates_payment(self):
		with patch("payments.services.PesapalService.create_payment") as mock_create_payment:
			mock_create_payment.return_value = {
				"provider": Payment.Provider.PESAPAL,
				"merchant_reference": self.order.merchant_reference,
				"redirect_url": "https://cybqa.pesapal.com/pesapaliframe/checkout/abc",
				"provider_reference": self.order.merchant_reference,
				"provider_tracking_id": "tracking-001",
				"status": Payment.Status.PENDING,
				"request_payload": {"id": self.order.merchant_reference},
				"response_payload": {"status": "200"},
			}
			response = self.client.post(
				"/api/payments/",
				data={"order_reference": str(self.order.reference), "provider": "PESAPAL"},
				format="json",
			)

		self.assertEqual(response.status_code, 201)
		self.assertEqual(response.data["amount"], "120.00")

	def test_get_order_payments_returns_created_payments(self):
		with patch("payments.services.PesapalService.create_payment") as mock_create_payment:
			mock_create_payment.return_value = {
				"provider": Payment.Provider.PESAPAL,
				"merchant_reference": self.order.merchant_reference,
				"redirect_url": "https://cybqa.pesapal.com/pesapaliframe/checkout/abc",
				"provider_reference": self.order.merchant_reference,
				"provider_tracking_id": "tracking-002",
				"status": Payment.Status.PENDING,
				"request_payload": {"id": self.order.merchant_reference},
				"response_payload": {"status": "200"},
			}
			payment = PaymentService.initiate_payment(
				order_reference=str(self.order.reference),
				provider=Payment.Provider.PESAPAL,
			)

		response = self.client.get(f"/api/payments/order/{self.order.reference}/")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data[0]["reference"], str(payment.reference))
