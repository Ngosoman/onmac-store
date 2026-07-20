from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
	order_reference = serializers.UUIDField(source="order.reference", read_only=True)

	class Meta:
		model = Payment
		fields = (
			"reference",
			"order_reference",
			"provider",
			"status",
			"amount",
			"currency",
			"redirect_url",
			"provider_reference",
			"provider_tracking_id",
			"created_at",
			"updated_at",
		)
		read_only_fields = fields


class PaymentInitiationSerializer(serializers.Serializer):
	order_reference = serializers.UUIDField()
	provider = serializers.ChoiceField(choices=Payment.Provider.choices, default=Payment.Provider.PESAPAL)
