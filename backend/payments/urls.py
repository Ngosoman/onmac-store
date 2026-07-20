from django.urls import path

from .views import (
	OrderPaymentListAPIView,
	PaymentCallbackAPIView,
	PaymentDetailAPIView,
	PaymentIPNAPIView,
	PaymentInitiationAPIView,
)

urlpatterns = [
    path("", PaymentInitiationAPIView.as_view(), name="payment-initiate"),
    path("callback/", PaymentCallbackAPIView.as_view(), name="payment-callback"),
    path("ipn/", PaymentIPNAPIView.as_view(), name="payment-ipn"),
    path("<uuid:reference>/", PaymentDetailAPIView.as_view(), name="payment-detail"),
    path("order/<uuid:order_reference>/", OrderPaymentListAPIView.as_view(), name="order-payment-list"),
]
