from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction
from rest_framework import serializers

from .models import Order, OrderItem


class OrderService:
	"""Application service responsible for order creation workflows."""

	MONEY_PRECISION = Decimal("0.01")

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

