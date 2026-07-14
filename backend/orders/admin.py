from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
	model = OrderItem
	extra = 0
	fields = ("product_id", "product_name", "quantity", "unit_price", "subtotal")
	readonly_fields = ("subtotal",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
	list_display = ("id", "reference", "merchant_reference", "currency", "pesapal_tracking_id", "customer_email", "status", "total_amount", "created_at")
	list_filter = ("status", "created_at")
	search_fields = ("reference", "merchant_reference", "pesapal_tracking_id", "customer_name", "customer_email")
	readonly_fields = ("reference",)
	inlines = [OrderItemInline]

# Register your models here.
