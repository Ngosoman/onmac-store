from rest_framework import serializers

from .models import Order, OrderItem
from .services import OrderService


PAYMENT_METHOD_CHOICES = (
	("PESAPAL", "PESAPAL"),
	("MPESA", "MPESA"),
	("AIRTEL", "AIRTEL"),
	("MASTERCARD", "MASTERCARD"),
	("VISACARDS", "VISACARDS"),
	("PAYONEER", "PAYONEER"),
	("PAYPAL", "PAYPAL"),
	("AIRTM", "AIRTM"),
	("NETELLER", "NETELLER"),
	("MONEYGO", "MONEYGO"),
	("SKRILL", "SKRILL"),
	("BINANCEPAY", "BINANCEPAY"),
	("CASHAPP", "CASHAPP"),
	("VENMO", "VENMO"),
	("APPLEPAY", "APPLEPAY"),
	("ALIPAY", "ALIPAY"),
	("KUCHINGA_VOUCHERS", "KUCHINGA_VOUCHERS"),
	("CRYPTOCURRENCY", "CRYPTOCURRENCY"),
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

	def validate(self, attrs):
		if attrs.get("quantity", 1) <= 0:
			raise serializers.ValidationError({"quantity": "Quantity must be greater than zero."})
		if "unit_price" in attrs and attrs["unit_price"] <= 0:
			raise serializers.ValidationError({"unit_price": "Unit price must be greater than zero."})
		return attrs


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
			"id",
			"reference",
			"merchant_reference",
			"pesapal_tracking_id",
			"status",
			"total_amount",
			"created_at",
			"updated_at",
		)

	def validate_items(self, items):
		if not items:
			raise serializers.ValidationError("At least one order item is required.")
		return items

	def validate(self, attrs):
		if self.instance and self.instance.status == Order.Status.PAID:
			raise serializers.ValidationError({"status": "Paid orders cannot be modified."})
		return attrs

	def create(self, validated_data):
		return OrderService.create_order(validated_data)
