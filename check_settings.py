import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django; django.setup()
from django.conf import settings

print("PayPal Client ID:", settings.PAYPAL_CLIENT_ID[:10] + "..." if settings.PAYPAL_CLIENT_ID else "NOT SET")
print("PayPal Client Secret:", "SET (hidden)" if settings.PAYPAL_CLIENT_SECRET else "NOT SET")
print("PayPal Mode:", settings.PAYPAL_MODE)
print("PayPal Return URL:", settings.PAYPAL_RETURN_URL)
print("PayPal Cancel URL:", settings.PAYPAL_CANCEL_URL)
print("PayPal Webhook ID:", settings.PAYPAL_WEBHOOK_ID if settings.PAYPAL_WEBHOOK_ID else "NOT SET")
print("Frontend Result URL:", settings.FRONTEND_PAYMENT_RESULT_URL)

# Test DNS resolution for PayPal
import socket
try:
    ip = socket.gethostbyname("api-m.sandbox.paypal.com")
    print(f"DNS Resolution: api-m.sandbox.paypal.com -> {ip}")
except Exception as e:
    print(f"DNS Resolution FAILED: {e}")

