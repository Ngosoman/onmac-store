from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction
from rest_framework import serializers

from orders.models import Order

from .models import Payment


class PesapalService:
	"""Pesapal adapter placeholder for future external API integration."""

	@staticmethod
	def create_payment(order: Order, payment: Payment) -> dict[str, Any]:
		return {
			"provider": Payment.Provider.PESAPAL,
			"merchant_reference": order.merchant_reference,
			"redirect_url": f"https://pay.pesapal.example/checkout/{payment.reference}",
			"provider_reference": order.merchant_reference,
			"provider_tracking_id": None,
			"status": Payment.Status.PENDING,
			"request_payload": {
				"order_reference": str(order.reference),
				"amount": str(order.total_amount),
				"currency": order.currency,
				"customer_email": order.customer_email,
			},
			"response_payload": {
				"message": "Pesapal checkout session initialized.",
			},
		}


class PaymentService:
	"""Application service for payment initiation and provider orchestration."""

	@staticmethod
	def _get_order(order_reference: str) -> Order:
		try:
			return Order.objects.prefetch_related("items").get(reference=order_reference)
		except Order.DoesNotExist as exc:
			raise serializers.ValidationError({"order_reference": ["Order not found."]}) from exc

	@staticmethod
	def _validate_order_for_payment(order: Order) -> None:
		if not order.items.exists():
			raise serializers.ValidationError({"order_reference": ["Cannot initiate payment for an empty order."]})
		if order.total_amount <= 0:
			raise serializers.ValidationError({"order_reference": ["Cannot initiate payment for an order with zero total."]})
		if order.status == Order.Status.PAID:
			raise serializers.ValidationError({"order_reference": ["This order has already been paid."]})
		if order.status == Order.Status.CANCELLED:
			raise serializers.ValidationError({"order_reference": ["Cancelled orders cannot be paid."]})

	@staticmethod
	def _get_provider_adapter(provider: str):
		if provider == Payment.Provider.PESAPAL:
			return PesapalService
		raise serializers.ValidationError({"provider": ["Unsupported payment provider."]})

	@staticmethod
	@transaction.atomic
	def initiate_payment(*, order_reference: str, provider: str) -> Payment:
		order = PaymentService._get_order(order_reference)
		PaymentService._validate_order_for_payment(order)

		try:
			payment = Payment.objects.create(
				order=order,
				provider=provider,
				amount=order.total_amount,
				currency=order.currency,
			)
			provider_adapter = PaymentService._get_provider_adapter(provider)
			provider_result = provider_adapter.create_payment(order, payment)

			payment.redirect_url = provider_result.get("redirect_url", "")
			payment.provider_reference = provider_result.get("provider_reference")
			payment.provider_tracking_id = provider_result.get("provider_tracking_id")
			payment.status = provider_result.get("status", Payment.Status.PENDING)
			payment.checkout_request = provider_result.get("request_payload", {})
			payment.checkout_response = provider_result.get("response_payload", {})
			payment.save(
				update_fields=[
					"redirect_url",
					"provider_reference",
					"provider_tracking_id",
					"status",
					"checkout_request",
					"checkout_response",
					"updated_at",
				]
			)

			order.payment_method = provider
			if payment.provider_tracking_id:
				order.pesapal_tracking_id = payment.provider_tracking_id
			order.save(update_fields=["payment_method", "pesapal_tracking_id", "updated_at"])

			return payment
		except serializers.ValidationError:
			raise
		except IntegrityError as exc:
			raise serializers.ValidationError({"detail": ["Unable to initialize payment right now."]}) from exc