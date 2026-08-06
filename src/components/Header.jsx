export default function Header({ cartCount }) {
  return (
    <header className="site-header">
      <div className="header-top">
        <a className="brand-wrap" href="#products" aria-label="Go to products">
          <span className="brand-kicker">Onmac Liquor Store</span>
        </a>
        <a
          className={`cart-pill${cartCount > 0 ? ' cart-pill--active' : ''}`}
          href="#cart"
          aria-label={`${cartCount} items in cart`}
        >
          Cart ({cartCount})
        </a>
      </div>

      <div className="header-menu-row">
        <nav aria-label="Catalog categories" className="shop-menu">
          <a href="#products">Spirits</a>
          <a href="#products">Wine</a>
          <a href="#products">Beer</a>
          <a href="#products">Accessories</a>
        </nav>

        <div className="header-search" role="search">
          <span>Search Wine &amp; Liquor</span>
          <a href="#products" className="header-search-link" aria-label="Go to product search">
            Search
          </a>
        </div>

        <nav aria-label="Store links" className="secondary-links">
          <a href="#checkout">Checkout</a>
          <a href="#cart">Track Order</a>
          <a href="#products">Corporate Gifts</a>
        </nav>
      </div>
    </header>
  );
}
