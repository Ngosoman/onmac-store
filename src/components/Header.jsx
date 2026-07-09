export default function Header({ cartCount }) {
  return (
    <header className="site-header">
      <div>
        <p className="brand-kicker">Onmacc</p>
        <h1>Liquor Store</h1>
      </div>
      <nav aria-label="Primary" className="site-nav">
        <a href="#products">Products</a>
        <a href="#checkout">Checkout</a>
        <span className="cart-pill" aria-label={`${cartCount} items in cart`}>
          Cart {cartCount}
        </span>
      </nav>
    </header>
  );
}
