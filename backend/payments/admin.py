from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
	list_display = ("reference", "order", "provider", "status", "amount", "currency", "created_at")
	list_filter = ("provider", "status", "currency", "created_at")
	search_fields = ("reference", "provider_reference", "provider_tracking_id", "order__reference", "order__customer_email")
	readonly_fields = ("reference", "created_at", "updated_at")
