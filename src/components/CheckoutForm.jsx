export default function CheckoutForm() {
  return (
    <form className="checkout-form">
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
