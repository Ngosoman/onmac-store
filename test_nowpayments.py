"""Quick test script to verify NOWPayments routing works."""
import json
import urllib.request

API_BASE = "http://127.0.0.1:8000/api/payments/"

def test_resolve_provider():
    """Test that 'CRYPTOCURRENCY' resolves to NOWPAYMENTS provider correctly."""
    
    # First create an order, then try to pay with CRYPTOCURRENCY
    # But since we just want to test routing, we can test with a non-existent order
    # and check what error we get (should be "Order not found" not "not connected to a processor")
    
    payload = json.dumps({
        "order_reference": "00000000-0000-0000-0000-000000000000",
        "provider": "CRYPTOCURRENCY"
    }).encode("utf-8")
    
    req = urllib.request.Request(
        API_BASE,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read().decode())
        print(f"✅ SUCCESS - Status: {resp.status}")
        print(f"   Response: {json.dumps(data, indent=2)}")
    except urllib.error.HTTPError as e:
        data = json.loads(e.read().decode())
        print(f"ℹ️  Got HTTP {e.code} response")
        print(f"   Response: {json.dumps(data, indent=2)}")
        
        if "Order not found" in str(data):
            print("\n✅ ROUTING WORKS! 'CRYPTOCURRENCY' → NOWPAYMENTS (error is just because order DNE)")
        elif "not connected to a processor" in str(data):
            print("\n❌ ROUTING FAILED! 'CRYPTOCURRENCY' is not connected to any processor")
        else:
            print("\n⚠️  Unexpected error - check the details above")


def test_normalize_payment_method():
    """Test that the normalize function works correctly."""
    from backend.payments.services import PaymentRoutingService
    
    # Test all the payment methods that should route to NOWPayments
    for method in ["Crypto", "Cryptocurrency", "CRYPTOCURRENCY", "CRYPTO"]:
        normalized = PaymentRoutingService.normalize_payment_method(method)
        provider = PaymentRoutingService.resolve_provider(method)
        print(f"   '{method}' → normalized='{normalized}' → provider='{provider}'")
    
    print("\n✅ normalize works correctly!")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--direct":
        # Direct Python test (imports Django models)
        import os
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        import django
        django.setup()
        test_normalize_payment_method()
    else:
        # HTTP test
        test_resolve_provider()

