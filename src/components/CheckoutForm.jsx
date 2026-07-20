import { useState } from 'react';
import { paymentMethodGroups } from '../data/paymentMethods';

const PESAPAL_SUPPORTED_METHODS = new Set(['Mpesa', 'Airtel', 'Mastercard', 'Visacards']);

export default function CheckoutForm({ cartItems }) {
  const [selectedMethod, setSelectedMethod] = useState('Mpesa');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  function parseUnitPrice(rawPrice) {
    const numericValue = Number.parseFloat(String(rawPrice).replace(/[^0-9.]/g, ''));
    return Number.isFinite(numericValue) ? numericValue.toFixed(2) : '0.00';
  }

  async function submitOrderAndRedirect(orderPayload) {
    const orderResponse = await fetch('/api/orders/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(orderPayload),
    });

    const createdOrder = await orderResponse.json();
    if (!orderResponse.ok) {
      throw new Error(createdOrder?.detail?.[0] || 'Failed to create order.');
    }

    const paymentResponse = await fetch('/api/payments/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        order_reference: createdOrder.reference,
        provider: 'PESAPAL',
      }),
    });

    const createdPayment = await paymentResponse.json();
    if (!paymentResponse.ok) {
      throw new Error(createdPayment?.detail?.[0] || 'Failed to initialize payment.');
    }

    if (!createdPayment.redirect_url) {
      throw new Error('Payment link is missing.');
    }

    window.location.assign(createdPayment.redirect_url);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setErrorMessage('');

    if (cartItems.length === 0) {
      setErrorMessage('Your cart is empty. Add items before checkout.');
      return;
    }

    if (!PESAPAL_SUPPORTED_METHODS.has(selectedMethod)) {
      setErrorMessage('For now, only Mpesa, Airtel, Mastercard, and Visacards are supported via Pesapal.');
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
      payment_method: 'PESAPAL',
      currency: 'KES',
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
                  <label key={method} className="payment-option">
                    <input
                      type="radio"
                      name="paymentMethod"
                      value={method}
                      checked={selectedMethod === method}
                      onChange={() => setSelectedMethod(method)}
                    />
                    <span>{method}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
        </div>
        <p className="payment-note">Selected payment method: {selectedMethod}</p>
        <p className="payment-note">
          Mpesa, Airtel, Mastercard, and Visacards are processed securely on Pesapal after redirect.
        </p>
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
        {isSubmitting ? 'Redirecting to Pesapal...' : 'Place order'}
      </button>
    </form>
  );
}
