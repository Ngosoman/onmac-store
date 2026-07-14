from django.db import models


class Order(models.Model):
	class Status(models.TextChoices):
		PENDING = "pending", "Pending"
		PAID = "paid", "Paid"
		FAILED = "failed", "Failed"
		CANCELLED = "cancelled", "Cancelled"

	customer_name = models.CharField(max_length=120)
	customer_email = models.EmailField()
	customer_phone = models.CharField(max_length=30, blank=True)
	shipping_address = models.TextField(blank=True)
	payment_method = models.CharField(max_length=50, blank=True)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
	total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f"Order #{self.id} - {self.customer_email}"


class OrderItem(models.Model):
	order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
	product_name = models.CharField(max_length=150)
	quantity = models.PositiveIntegerField(default=1)
	unit_price = models.DecimalField(max_digits=10, decimal_places=2)

	def __str__(self):
		return f"{self.product_name} x {self.quantity}"
