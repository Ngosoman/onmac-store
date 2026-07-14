from rest_framework import serializers

from .models import Order, OrderItem


PAYMENT_METHOD_CHOICES = (
	("PESAPAL", "PESAPAL"),
	("CARD", "CARD"),
	("MPESA", "MPESA"),
	("BANK", "BANK"),
)


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
	items = OrderItemSerializer(many=True, required=True, allow_empty=False)
	payment_method = serializers.ChoiceField(choices=PAYMENT_METHOD_CHOICES, allow_blank=True, required=False)

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
