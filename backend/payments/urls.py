from django.urls import path

from .views import (
    OrderPaymentListAPIView,
    PaymentCallbackAPIView,
    PaymentDetailAPIView,
    PaymentIPNAPIView,
    PaymentInitiationAPIView,
    PayPalCaptureAPIView,
    PayPalWebhookAPIView,
    StripeSuccessAPIView,
    StripeWebhookAPIView,
)

urlpatterns = [
    path("", PaymentInitiationAPIView.as_view(), name="payment-initiate"),
    path("callback/", PaymentCallbackAPIView.as_view(), name="payment-callback"),
    path("ipn/", PaymentIPNAPIView.as_view(), name="payment-ipn"),
    path("paypal/capture/", PayPalCaptureAPIView.as_view(), name="paypal-capture"),
    path("paypal/webhook/", PayPalWebhookAPIView.as_view(), name="paypal-webhook"),
    path("stripe/webhook/", StripeWebhookAPIView.as_view(), name="stripe-webhook"),
    path("stripe/success/", StripeSuccessAPIView.as_view(), name="stripe-success"),
    path("<uuid:reference>/", PaymentDetailAPIView.as_view(), name="payment-detail"),
    path("order/<uuid:order_reference>/", OrderPaymentListAPIView.as_view(), name="order-payment-list"),
]

