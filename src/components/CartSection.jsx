export default function CartSection({
  cartItems,
  onIncreaseItem,
  onDecreaseItem,
  onRemoveItem,
  onProceedToCheckout,
}) {
  const itemCount = cartItems.reduce((total, item) => total + item.quantity, 0);

  return (
    <section className="cart-section" id="cart">
      <div className="section-heading">
        <p className="eyebrow">Cart</p>
        <h2>Review items before checkout</h2>
      </div>

      <div className="cart-panel">
        {cartItems.length > 0 ? (
          <>
            <ul className="cart-list">
              {cartItems.map((item) => (
                <li key={item.id} className="cart-row">
                  <div>
                    <strong>{item.product?.name}</strong>
                    <p>
                      {item.product?.category} · {item.product?.price}
                    </p>
                  </div>
                  <div className="cart-row-actions">
                    <button type="button" onClick={() => onDecreaseItem(item.id)}>
                      -
                    </button>
                    <span>{item.quantity}</span>
                    <button type="button" onClick={() => onIncreaseItem(item.id)}>
                      +
                    </button>
                    <button type="button" className="ghost-button" onClick={() => onRemoveItem(item.id)}>
                      Remove
                    </button>
                  </div>
                </li>
              ))}
            </ul>
            <div className="cart-footer">
              <p>{itemCount} item{itemCount === 1 ? '' : 's'} in cart</p>
              <button type="button" className="submit-button" onClick={onProceedToCheckout}>
                Proceed to checkout
              </button>
            </div>
          </>
        ) : (
          <div className="empty-cart">
            <p>Your cart is empty.</p>
            <button type="button" className="submit-button" onClick={onProceedToCheckout}>
              Go to checkout
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
