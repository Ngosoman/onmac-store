from decimal import Decimal

from rest_framework import serializers

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
	line_total = serializers.SerializerMethodField()

	class Meta:
		model = OrderItem
		fields = (
			"id",
			"product_id",
			"product_name",
			"quantity",
			"unit_price",
			"subtotal",
			"line_total",
		)
		read_only_fields = ("subtotal", "line_total")

	def get_line_total(self, obj):
		return str(obj.subtotal)


class OrderSerializer(serializers.ModelSerializer):
	items = OrderItemSerializer(many=True, required=False)

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
			"id",
			"reference",
			"total_amount",
			"created_at",
			"updated_at",
		)

	def validate_items(self, items):
		if not items:
			raise serializers.ValidationError("At least one order item is required.")
		return items

	def create(self, validated_data):
		items_data = validated_data.pop("items", [])
		order = Order.objects.create(**validated_data)
		total_amount = Decimal("0")

		for item_data in items_data:
			item = OrderItem.objects.create(order=order, **item_data)
			total_amount += item.subtotal

		order.total_amount = total_amount
		order.save(update_fields=["total_amount", "updated_at"])
		return order

	def update(self, instance, validated_data):
		items_data = validated_data.pop("items", None)

		for attr, value in validated_data.items():
			setattr(instance, attr, value)

		if items_data is not None:
			instance.items.all().delete()
			total_amount = Decimal("0")
			for item_data in items_data:
				item = OrderItem.objects.create(order=instance, **item_data)
				total_amount += item.subtotal
			instance.total_amount = total_amount

		instance.save()
		return instance