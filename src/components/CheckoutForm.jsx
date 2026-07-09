import { useState } from 'react';
import { paymentMethodGroups } from '../data/paymentMethods';

export default function CheckoutForm({ cartItems }) {
  const [selectedMethod, setSelectedMethod] = useState('Mpesa');

  return (
    <form className="checkout-form">
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
      </div>
      <div className="form-grid">
        <label>
          First name
          <input type="text" name="firstName" />
        </label>
        <label>
          Last name
          <input type="text" name="lastName" />
        </label>
        <label>
          Email
          <input type="email" name="email" />
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
      <button className="submit-button" type="submit">
        Place order
      </button>
    </form>
  );
}
