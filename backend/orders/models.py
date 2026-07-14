import uuid

from django.db import models


class Order(models.Model):
	class Status(models.TextChoices):
		PENDING = "pending", "Pending"
		PAID = "paid", "Paid"
		FAILED = "failed", "Failed"
		CANCELLED = "cancelled", "Cancelled"

	class Currency(models.TextChoices):
		KES = "KES", "KES"
		USD = "USD", "USD"
		GBP = "GBP", "GBP"

	reference = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
	merchant_reference = models.CharField(max_length=100, blank=True, null=True, unique=True)
	customer_name = models.CharField(max_length=120)
	customer_email = models.EmailField()
	customer_phone = models.CharField(max_length=30, blank=True)
	shipping_address = models.TextField(blank=True)
	payment_method = models.CharField(max_length=50, blank=True)
	pesapal_tracking_id = models.CharField(max_length=100, blank=True, null=True)
	currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.KES)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
	total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f"Order {self.reference} - {self.customer_email}"

	def save(self, *args, **kwargs):
		if not self.merchant_reference:
			self.merchant_reference = self._generate_merchant_reference()
		super().save(*args, **kwargs)

	def _generate_merchant_reference(self):
		base_reference = f"MR-{uuid.uuid4().hex[:12].upper()}"
		while Order.objects.filter(merchant_reference=base_reference).exists():
			base_reference = f"MR-{uuid.uuid4().hex[:12].upper()}"
		return base_reference


class OrderItem(models.Model):
	order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
	product_name = models.CharField(max_length=150)
	quantity = models.PositiveIntegerField(default=1)
	unit_price = models.DecimalField(max_digits=10, decimal_places=2)

	def __str__(self):
		return f"{self.product_name} x {self.quantity}"
