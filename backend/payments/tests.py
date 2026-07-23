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

	def test_initiate_payment_uses_nowpayments_adapter(self):
		with patch("payments.services.NowPaymentsService.create_payment") as mock_create_payment:
			mock_create_payment.return_value = {
				"provider": Payment.Provider.NOWPAYMENTS,
				"merchant_reference": self.order.merchant_reference,
				"redirect_url": "https://nowpayments.io/payment/abc",
				"provider_reference": "invoice-001",
				"provider_tracking_id": "invoice-001",
				"status": Payment.Status.PENDING,
				"request_payload": {"order_id": str(self.order.reference)},
				"response_payload": {"payment_id": "invoice-001", "status": "pending"},
			}
			payment = PaymentService.initiate_payment(
				order_reference=str(self.order.reference),
				provider=Payment.Provider.NOWPAYMENTS,
			)

		self.assertEqual(payment.provider, Payment.Provider.NOWPAYMENTS)
		self.assertEqual(payment.status, Payment.Status.PENDING)
		self.assertEqual(payment.provider_reference, "invoice-001")


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

	def test_callback_endpoint_updates_payment_and_order_status(self):
		payment = Payment.objects.create(
			order=self.order,
			provider=Payment.Provider.PESAPAL,
			status=Payment.Status.PENDING,
			amount=self.order.total_amount,
			currency=self.order.currency,
			provider_reference=self.order.merchant_reference,
			provider_tracking_id="track-callback-001",
		)

		with patch("payments.services.PesapalService.verify_transaction") as mock_verify:
			mock_verify.return_value = {
				"payment_status_description": "Completed",
				"status": "200",
			}
			response = self.client.get(
				f"/api/payments/callback/?OrderTrackingId={payment.provider_tracking_id}&OrderMerchantReference={self.order.merchant_reference}&OrderNotificationType=CALLBACKURL"
			)

		payment.refresh_from_db()
		self.order.refresh_from_db()

		self.assertEqual(response.status_code, 302)
		self.assertIn("payment-result", response["Location"])
		self.assertEqual(payment.status, Payment.Status.COMPLETED)
		self.assertEqual(self.order.status, Order.Status.PAID)

	def test_ipn_endpoint_updates_failed_status(self):
		payment = Payment.objects.create(
			order=self.order,
			provider=Payment.Provider.PESAPAL,
			status=Payment.Status.PENDING,
			amount=self.order.total_amount,
			currency=self.order.currency,
			provider_reference=self.order.merchant_reference,
			provider_tracking_id="track-ipn-001",
		)

		with patch("payments.services.PesapalService.verify_transaction") as mock_verify:
			mock_verify.return_value = {
				"payment_status_description": "Failed",
				"status": "200",
			}
			response = self.client.post(
				"/api/payments/ipn/",
				data={
					"OrderTrackingId": payment.provider_tracking_id,
					"OrderMerchantReference": self.order.merchant_reference,
					"OrderNotificationType": "IPNCHANGE",
				},
				format="json",
			)

		payment.refresh_from_db()
		self.order.refresh_from_db()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payment.status, Payment.Status.FAILED)
		self.assertEqual(self.order.status, Order.Status.FAILED)

	def test_nowpayments_webhook_marks_payment_completed_and_order_paid(self):
		payment = Payment.objects.create(
			order=self.order,
			provider=Payment.Provider.NOWPAYMENTS,
			status=Payment.Status.PENDING,
			amount=self.order.total_amount,
			currency=self.order.currency,
			provider_reference="invoice-900",
		)

		with patch("payments.services.NowPaymentsService.verify_payment") as mock_verify:
			mock_verify.return_value = {
				"payment_id": "invoice-900",
				"payment_status": "finished",
				"order_id": str(self.order.reference),
			}
			response = self.client.post(
				"/api/payments/ipn/",
				data={
					"payment_id": "invoice-900",
					"payment_status": "finished",
					"order_id": str(self.order.reference),
				},
				format="json",
			)

		payment.refresh_from_db()
		self.order.refresh_from_db()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payment.status, Payment.Status.COMPLETED)
		self.assertEqual(self.order.status, Order.Status.PAID)
