from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from .models import Order, OrderItem


class OrderService:
	@staticmethod
	def _calculate_total(items):
		return sum((item.subtotal for item in items), Decimal("0"))

	@staticmethod
	@transaction.atomic
	def create_order(validated_data):
		items_data = validated_data.pop("items")
		order = Order.objects.create(**validated_data)
		created_items = []

		for item_data in items_data:
			created_items.append(OrderItem.objects.create(order=order, **item_data))

		order.total_amount = OrderService._calculate_total(created_items)
		order.save(update_fields=["total_amount", "updated_at"])
		return order

	@staticmethod
	@transaction.atomic
	def update_order(order, validated_data):
		if order.status == Order.Status.PAID:
			raise serializers.ValidationError({"status": "Paid orders cannot be modified."})

		items_data = validated_data.pop("items", None)

		for attr, value in validated_data.items():
			setattr(order, attr, value)

		if items_data is not None:
			order.items.all().delete()
			created_items = []
			for item_data in items_data:
				created_items.append(OrderItem.objects.create(order=order, **item_data))
			order.total_amount = OrderService._calculate_total(created_items)

		order.save()
		return order
