from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from rest_framework import serializers

from .models import Order, OrderItem


class OrderService:
	"""Application service responsible for order creation workflows."""

	MONEY_PRECISION = Decimal("0.01")
	PESAPAL_METHODS = {"PESAPAL", "MPESA", "AIRTEL", "MASTERCARD", "VISACARDS"}

	@staticmethod
	def _normalize_payment_method(payment_method: Any) -> str:
		return str(payment_method or "").strip().upper().replace(" ", "_")

	@staticmethod
	def _is_pesapal_method(payment_method: Any) -> bool:
		return OrderService._normalize_payment_method(payment_method) in OrderService.PESAPAL_METHODS

	@staticmethod
	def _usd_to_kes_rate() -> Decimal:
		rate = Decimal(str(getattr(settings, "USD_TO_KES_RATE", "129")))
		if rate <= 0:
			raise serializers.ValidationError({"detail": ["USD_TO_KES_RATE must be greater than zero."]})
		return rate

	@staticmethod
	def _apply_pesapal_currency_guard(*, order_data: dict[str, Any], items_data: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
		if not OrderService._is_pesapal_method(order_data.get("payment_method")):
			return order_data, items_data

		currency = str(order_data.get("currency") or "").strip().upper()
		if not currency:
			currency = Order.Currency.KES

		if currency == Order.Currency.KES:
			order_data["currency"] = Order.Currency.KES
			return order_data, items_data

		if currency != Order.Currency.USD:
			raise serializers.ValidationError(
				{"currency": ["Pesapal payments support USD input conversion to KES or direct KES only."]}
			)

		rate = OrderService._usd_to_kes_rate()
		converted_items: list[dict[str, Any]] = []
		for item in items_data:
			converted_item = dict(item)
			unit_price = Decimal(str(item["unit_price"]))
			converted_item["unit_price"] = (unit_price * rate).quantize(OrderService.MONEY_PRECISION)
			converted_items.append(converted_item)

		order_data["currency"] = Order.Currency.KES
		return order_data, converted_items

	@staticmethod
	def _calculate_item_subtotal(*, quantity: int, unit_price: Decimal) -> Decimal:
		return (unit_price * quantity).quantize(OrderService.MONEY_PRECISION)

	@staticmethod
	def _calculate_order_total(created_items: list[OrderItem]) -> Decimal:
		return sum((item.subtotal for item in created_items), Decimal("0.00")).quantize(OrderService.MONEY_PRECISION)

	@staticmethod
	def _create_order_items(*, order: Order, items_data: list[dict[str, Any]]) -> list[OrderItem]:
		created_items: list[OrderItem] = []
		for item_data in items_data:
			quantity = item_data["quantity"]
			unit_price = Decimal(item_data["unit_price"])
			subtotal = OrderService._calculate_item_subtotal(quantity=quantity, unit_price=unit_price)
			created_items.append(
				OrderItem.objects.create(
					order=order,
					product_id=item_data.get("product_id"),
					product_name=item_data["product_name"],
					quantity=quantity,
					unit_price=unit_price,
					subtotal=subtotal,
				)
			)
		return created_items

	@staticmethod
	@transaction.atomic
	def create_order(validated_data: dict[str, Any]) -> Order:
		"""Create an order and its items atomically from validated serializer data."""

		order_data = validated_data.copy()
		items_data = order_data.pop("items", [])

		if not items_data:
			raise serializers.ValidationError({"items": ["At least one order item is required."]})

		order_data, items_data = OrderService._apply_pesapal_currency_guard(order_data=order_data, items_data=items_data)

		try:
			order = Order.objects.create(**order_data)
			created_items = OrderService._create_order_items(order=order, items_data=items_data)
			order.total_amount = OrderService._calculate_order_total(created_items)
			order.save(update_fields=["total_amount", "updated_at"])
			return order
		except serializers.ValidationError:
			raise
		except IntegrityError as exc:
			raise serializers.ValidationError({"detail": ["Unable to create the order right now."]}) from exc

	@staticmethod
	@transaction.atomic
	def update_order(order: Order, validated_data: dict[str, Any]) -> Order:
		"""Update a mutable order while recalculating totals for replaced items."""

		if order.status == Order.Status.PAID:
			raise serializers.ValidationError({"status": "Paid orders cannot be modified."})

		order_data = validated_data.copy()
		items_data = order_data.pop("items", None)

		if items_data is not None and items_data:
			guard_order_data = {
				"payment_method": order_data.get("payment_method", order.payment_method),
				"currency": order_data.get("currency", order.currency),
			}
			guard_order_data, items_data = OrderService._apply_pesapal_currency_guard(
				order_data=guard_order_data,
				items_data=items_data,
			)
			order_data["currency"] = guard_order_data["currency"]

		for field_name, value in order_data.items():
			setattr(order, field_name, value)

		if items_data is not None:
			if not items_data:
				raise serializers.ValidationError({"items": ["At least one order item is required."]})
			order.items.all().delete()
			created_items = OrderService._create_order_items(order=order, items_data=items_data)
			order.total_amount = OrderService._calculate_order_total(created_items)

		order.save()
		return order

