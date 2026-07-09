export default function CheckoutForm({ cartItems }) {
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
