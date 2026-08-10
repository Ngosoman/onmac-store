export default function Header({ cartCount, searchQuery, onSearchChange }) {
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

        <form
          className="header-search"
          role="search"
          onSubmit={(event) => {
            event.preventDefault();
            document.getElementById('products')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }}
        >
          <label htmlFor="header-product-search" className="header-search-label">Search Wine &amp; Liquor</label>
          <div className="header-search-controls">
            <input
              id="header-product-search"
              type="search"
              value={searchQuery}
              onChange={(event) => onSearchChange(event.target.value)}
              placeholder="Search products"
            />
            <button type="submit" className="header-search-link" aria-label="Search products">
              Search
            </button>
          </div>
        </form>

        <nav aria-label="Store links" className="secondary-links">
          <a href="#checkout">Checkout</a>
          <a href="#cart">Track Order</a>
          <a href="#products">Corporate Gifts</a>
        </nav>
      </div>
    </header>
  );
}
