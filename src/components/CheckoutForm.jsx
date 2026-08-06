import { useState } from 'react';
import { paymentMethodGroups } from '../data/paymentMethods';

const DEFAULT_PRODUCTION_API_BASE_URL = 'https://onmac-store.onrender.com';

function resolveApiBaseUrl() {
  const configured = String(import.meta.env.VITE_API_BASE_URL || '').trim();
  if (configured) {
    const normalized = configured.replace(/\/$/, '');
    return normalized;
  }

  if (import.meta.env.PROD) {
    return DEFAULT_PRODUCTION_API_BASE_URL;
  }

  return '';
}

const API_BASE_URL = resolveApiBaseUrl();

function apiUrl(path) {
  if (!API_BASE_URL) {
    return path;
  }
  return `${API_BASE_URL}${path}`;
}

async function parseApiResponse(response) {
  const contentType = String(response.headers.get('content-type') || '').toLowerCase();
  if (contentType.includes('application/json')) {
    return response.json();
  }

  const text = await response.text();
  return {
    detail: [text || `Request failed with status ${response.status}.`],
  };
}

function normalizePaymentMethod(method) {
  const trimmedMethod = String(method || '').trim();

  if (!trimmedMethod) {
    return '';
  }

  return trimmedMethod.toUpperCase();
}

const NOWPAYMENTS_METHODS = new Set(['Crypto', 'Cryptocurrency', 'NOWPayments']);
const PAYPAL_METHODS = new Set(['Paypal']);
const STRIPE_METHODS = new Set(['Stripe', 'Card', 'Credit Card', 'Debit Card', 'CREDIT_CARD', 'DEBIT_CARD', 'CARD']);

function isCryptoPayment(method) {
  return NOWPAYMENTS_METHODS.has(String(method || '').trim());
}

function isPayPalPayment(method) {
  return PAYPAL_METHODS.has(String(method || '').trim());
}

function isStripePayment(method) {
  const normalized = String(method || '').trim().toUpperCase().replace(/[^A-Z0-9]+/g, '');
  return STRIPE_METHODS.has(String(method || '').trim()) || normalized === 'STRIPE' || normalized === 'CARD' || normalized === 'CREDITCARD' || normalized === 'DEBITCARD';
}

function getCurrencyForPayment(method) {
  if (isPayPalPayment(method) || isStripePayment(method) || isCryptoPayment(method)) {
    return 'USD';
  }
  return 'KES';
}

export default function CheckoutForm({ cartItems }) {
  const [selectedMethod, setSelectedMethod] = useState('Mpesa');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const isCrypto = isCryptoPayment(selectedMethod);
  const isPayPal = isPayPalPayment(selectedMethod);
  const isStripe = isStripePayment(selectedMethod);

  function parseUnitPrice(rawPrice) {
    const numericValue = Number.parseFloat(String(rawPrice).replace(/[^0-9.]/g, ''));
    return Number.isFinite(numericValue) ? numericValue.toFixed(2) : '0.00';
  }

  function getRedirectLabel() {
    if (isCrypto) return 'Opening payment page...';
    if (isPayPal) return 'Redirecting to PayPal...';
    if (isStripe) return 'Redirecting to Stripe...';
    return 'Redirecting to Pesapal...';
  }

  function getPaymentDescription() {
    if (isCrypto) {
      return 'Cryptocurrency payments are processed via NOWPayments — you will receive an invoice link in a new tab.';
    }
    if (isPayPal) {
      return 'PayPal payments are processed securely on PayPal — you will be redirected to complete payment.';
    }
    if (isStripe) {
      return 'Card payments are processed securely on Stripe via hosted checkout.';
    }
    return 'Mpesa, Airtel, Mastercard, and Visacards are processed securely on Pesapal after redirect.';
  }

  function getCurrencyLabel() {
    return getCurrencyForPayment(selectedMethod);
  }

  async function submitOrderAndRedirect(orderPayload) {
    const orderResponse = await fetch(apiUrl('/api/orders/'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(orderPayload),
    });

    const createdOrder = await parseApiResponse(orderResponse);
    if (!orderResponse.ok) {
      throw new Error(createdOrder?.detail?.[0] || 'Failed to create order.');
    }

    const paymentResponse = await fetch(apiUrl('/api/payments/'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        order_reference: createdOrder.reference,
        provider: normalizePaymentMethod(selectedMethod),
      }),
    });

    const createdPayment = await parseApiResponse(paymentResponse);
    if (!paymentResponse.ok) {
      throw new Error(createdPayment?.detail?.[0] || 'Failed to initialize payment.');
    }

    if (!createdPayment.redirect_url) {
      throw new Error('Payment link is missing.');
    }

    if (isCrypto) {
      // NOWPayments — open invoice in new tab
      window.open(createdPayment.redirect_url, '_blank', 'noopener,noreferrer');
    } else {
      // PayPal, Stripe, or Pesapal — redirect to payment provider
      // For PayPal: customer approves on PayPal, then PayPal redirects to
      // PAYPAL_RETURN_URL which captures server-side and redirects to
      // FRONTEND_PAYMENT_RESULT_URL with status params.
      // For Stripe: the hosted checkout session redirects to the success URL.
      window.location.assign(createdPayment.redirect_url);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setErrorMessage('');

    if (cartItems.length === 0) {
      setErrorMessage('Your cart is empty. Add items before checkout.');
      return;
    }

    const formData = new FormData(event.currentTarget);
    const firstName = String(formData.get('firstName') || '').trim();
    const lastName = String(formData.get('lastName') || '').trim();
    const email = String(formData.get('email') || '').trim();
    const phone = String(formData.get('phone') || '').trim();
    const billingAddress = String(formData.get('billingAddress1') || '').trim();
    const city = String(formData.get('billingCity') || '').trim();
    const state = String(formData.get('billingState') || '').trim();

    if (!firstName || !lastName || !email) {
      setErrorMessage('First name, last name, and email are required.');
      return;
    }

    const customerName = `${firstName} ${lastName}`.trim();
    const shippingAddress = [billingAddress, city, state].filter(Boolean).join(', ');

    const orderPayload = {
      customer_name: customerName,
      customer_email: email,
      customer_phone: phone,
      shipping_address: shippingAddress,
      payment_method: normalizePaymentMethod(selectedMethod),
      currency: getCurrencyForPayment(selectedMethod),
      items: cartItems.map((item) => ({
        product_id: item.product?.id,
        product_name: item.product?.name || 'Unnamed Product',
        quantity: item.quantity,
        unit_price: parseUnitPrice(item.product?.price),
      })),
    };

    setIsSubmitting(true);
    try {
      await submitOrderAndRedirect(orderPayload);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Checkout failed. Please try again.');
      setIsSubmitting(false);
    }
  }

  return (
    <form className="checkout-form" onSubmit={handleSubmit}>
      <div className="cart-summary" aria-live="polite">
        <p className="eyebrow">Cart summary</p>
        {cartItems.length > 0 ? (
          <ul>
            {cartItems.map((item) => (
              <li key={item.id}>
                {item.product?.name} x {item.quantity}
              </li>
            ))}
          </ul>
        ) : (
          <p>Your cart is empty.</p>
        )}
      </div>
      <div className="payment-section">
        <p className="eyebrow">Payment method</p>
        <h3>Choose how you want to pay</h3>
        <div className="payment-groups">
          {paymentMethodGroups.map((group) => (
            <fieldset key={group.title} className="payment-group">
              <legend>{group.title}</legend>
              <div className="payment-options">
                {group.methods.map((method) => (
                  <label key={method.value} className="payment-option">
                    <input
                      type="radio"
                      name="paymentMethod"
                      value={method.value}
                      checked={selectedMethod === method.value}
                      onChange={() => setSelectedMethod(method.value)}
                    />
                    <span>{method.label}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
        </div>
        <p className="payment-note">Selected payment method: {selectedMethod}</p>
        <p className="payment-note">{getPaymentDescription()}</p>
        <p className="payment-note">All prices for this store are charged in {getCurrencyLabel()}.</p>
      </div>
      <div className="form-grid">
        <label>
          First name
          <input type="text" name="firstName" required />
        </label>
        <label>
          Last name
          <input type="text" name="lastName" required />
        </label>
        <label>
          Email
          <input type="email" name="email" required />
        </label>
        <label>
          Phone
          <input type="tel" name="phone" />
        </label>
        <label className="full-width">
          Billing address
          <input type="text" name="billingAddress1" />
        </label>
        <label>
          City
          <input type="text" name="billingCity" />
        </label>
        <label>
          State
          <input type="text" name="billingState" />
        </label>
      </div>
      {errorMessage ? <p className="payment-note">{errorMessage}</p> : null}
      <button className="submit-button" type="submit" disabled={isSubmitting}>
        {isSubmitting ? getRedirectLabel() : 'Place order'}
      </button>
    </form>
  );
}

