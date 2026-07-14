from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
	class Meta:
		model = OrderItem
		fields = (
			"id",
			"product_id",
			"product_name",
			"quantity",
			"unit_price",
			"subtotal",
		)
		read_only_fields = ("id", "subtotal")


class OrderSerializer(serializers.ModelSerializer):
	class PaymentMethodChoices(serializers.ChoiceField):
		def __init__(self, **kwargs):
			super().__init__(choices=("PESAPAL", "CARD", "MPESA", "BANK"), **kwargs)

	items = OrderItemSerializer(many=True, required=True)
	payment_method = PaymentMethodChoices(allow_blank=True, required=False)

	class Meta:
		model = Order
		fields = (
			"id",
			"reference",
			"merchant_reference",
			"customer_name",
			"customer_email",
			"customer_phone",
			"shipping_address",
			"payment_method",
			"pesapal_tracking_id",
			"currency",
			"status",
			"total_amount",
			"created_at",
			"updated_at",
			"items",
		)
		read_only_fields = (
			"reference",
			"merchant_reference",
			"pesapal_tracking_id",
			"total_amount",
			"created_at",
			"updated_at",
		)

	def validate_items(self, items):
		if not items:
			raise serializers.ValidationError("At least one order item is required.")
		return items

	def _recalculate_total(self, items):
		return sum((item.subtotal for item in items), Decimal("0"))

	@transaction.atomic
	def create(self, validated_data):
		items_data = validated_data.pop("items")
		order = Order.objects.create(**validated_data)
		created_items = []

		for item_data in items_data:
			created_items.append(OrderItem.objects.create(order=order, **item_data))

		order.total_amount = self._recalculate_total(created_items)
		order.save(update_fields=["total_amount", "updated_at"])
		return order

	@transaction.atomic
	def update(self, instance, validated_data):
		if instance.status == Order.Status.PAID:
			raise serializers.ValidationError({"status": "Paid orders cannot be modified."})

		items_data = validated_data.pop("items", None)

		for attr, value in validated_data.items():
			setattr(instance, attr, value)

		if items_data is not None:
			instance.items.all().delete()
			created_items = []
			for item_data in items_data:
				created_items.append(OrderItem.objects.create(order=instance, **item_data))
			instance.total_amount = self._recalculate_total(created_items)

		instance.save()
		return instance
