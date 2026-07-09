import { useMemo, useState } from 'react';
import { products } from '../data/products';

const categoryIcons = {
  Wine: '🍷',
  Beer: '🍺',
  Spirits: '🥃',
  'Non-Alcoholic': '🥤',
};

export default function ProductGrid({ onAddToCart }) {
  const [query, setQuery] = useState('');

  const filteredProducts = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    if (!normalizedQuery) {
      return products;
    }

    return products.filter((product) => {
      const searchableText = [product.name, product.category, product.size, product.note]
        .join(' ')
        .toLowerCase();

      return searchableText.includes(normalizedQuery);
    });
  }, [query]);

  return (
    <section className="products-section" id="products">
      <div className="section-heading">
        <p className="eyebrow">Featured</p>
        <h2>Products</h2>
      </div>
      <div className="product-search">
        <label className="search-field">
          Search products
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by name, category, size, or note"
          />
        </label>
        <div className="search-meta">
          <span>
            Showing {filteredProducts.length} of {products.length}
          </span>
          {query ? (
            <button type="button" className="ghost-button" onClick={() => setQuery('')}>
              Clear search
            </button>
          ) : null}
        </div>
      </div>
      <div className="product-grid">
        {filteredProducts.map((product) => (
          <article key={product.id} className="product-card">
            <div className="product-icon-badge" aria-hidden="true">
              <span>{categoryIcons[product.category] ?? '🥂'}</span>
            </div>
            <p className="product-category">{product.category}</p>
            <h3>{product.name}</h3>
            <p className="product-size">{product.size}</p>
            <p>{product.note}</p>
            <div className="product-footer">
              <strong>{product.price}</strong>
              <button type="button" onClick={() => onAddToCart(product)}>
                Add to cart
              </button>
            </div>
          </article>
        ))}
      </div>
      {filteredProducts.length === 0 ? (
        <div className="empty-products">
          <p>No products matched your search.</p>
        </div>
      ) : null}
    </section>
  );
}
