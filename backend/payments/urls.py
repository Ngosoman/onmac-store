from django.urls import path

from .views import OrderPaymentListAPIView, PaymentDetailAPIView, PaymentInitiationAPIView

urlpatterns = [
    path("", PaymentInitiationAPIView.as_view(), name="payment-initiate"),
    path("<uuid:reference>/", PaymentDetailAPIView.as_view(), name="payment-detail"),
    path("order/<uuid:order_reference>/", OrderPaymentListAPIView.as_view(), name="order-payment-list"),
]
