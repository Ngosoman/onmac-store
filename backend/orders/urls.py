from django.urls import path

from .views import health, order_detail, orders_collection

urlpatterns = [
    path("health/", health, name="orders-health"),
    path("", orders_collection, name="orders-collection"),
    path("<int:order_id>/", order_detail, name="order-detail"),
]
