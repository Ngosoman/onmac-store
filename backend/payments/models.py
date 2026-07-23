import uuid

from django.db import models

from orders.models import Order


class Payment(models.Model):
	class Provider(models.TextChoices):
		PESAPAL = "PESAPAL", "Pesapal"
		NOWPAYMENTS = "NOWPAYMENTS", "NOWPayments"

	class Status(models.TextChoices):
		INITIALIZED = "initialized", "Initialized"
		PENDING = "pending", "Pending"
		COMPLETED = "completed", "Completed"
		FAILED = "failed", "Failed"
		CANCELLED = "cancelled", "Cancelled"

	reference = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
	order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
	provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.PESAPAL)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.INITIALIZED)
	amount = models.DecimalField(max_digits=12, decimal_places=2)
	currency = models.CharField(max_length=3, choices=Order.Currency.choices)
	redirect_url = models.URLField(blank=True)
	provider_reference = models.CharField(max_length=120, blank=True, null=True, unique=True)
	provider_tracking_id = models.CharField(max_length=120, blank=True, null=True, unique=True)
	checkout_request = models.JSONField(default=dict, blank=True)
	checkout_response = models.JSONField(default=dict, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ("-created_at",)

	def __str__(self):
		return f"Payment {self.reference} for order {self.order.reference}"
