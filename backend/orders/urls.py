from django.urls import path

from .views import OrderDetailAPIView, OrderListCreateAPIView

urlpatterns = [
    path("", OrderListCreateAPIView.as_view(), name="order-list-create"),
    path("<uuid:reference>/", OrderDetailAPIView.as_view(), name="order-detail-by-reference"),
]
