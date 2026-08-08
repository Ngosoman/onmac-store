import { useMemo, useState } from 'react';
import { products } from '../data/products';

const categoryTypes = ['All', ...Array.from(new Set(products.map((product) => product.category)))];
const subcategoryTypes = ['All', ...Array.from(new Set(products.map((product) => product.subcategory)))];

const categoryEmblems = {
  Wine: 'W',
  Beer: 'B',
  Spirits: 'S',
  'Non-Alcoholic': 'N',
};

export default function ProductGrid({ onAddToCart }) {
  const [query, setQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState('All');
  const [activeSubcategory, setActiveSubcategory] = useState('All');
  const [imageErrors, setImageErrors] = useState({});

  const filteredProducts = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return products.filter((product) => {
      if (activeCategory !== 'All' && product.category !== activeCategory) {
        return false;
      }

      if (activeSubcategory !== 'All' && product.subcategory !== activeSubcategory) {
        return false;
      }

      if (!normalizedQuery) {
        return true;
      }

      const searchableText = [
        product.name,
        product.brand,
        product.category,
        product.subcategory,
        product.size,
        product.note,
        ...(product.tags || []),
      ]
        .join(' ')
        .toLowerCase();

      return searchableText.includes(normalizedQuery);
    });
  }, [activeCategory, activeSubcategory, query]);

  return (
    <section className="products-section" id="products">
      <div className="catalog-title-bar">
        <p className="eyebrow">Best selling</p>
        <h2>Wine &amp; Liquor</h2>
      </div>

      <div className="catalog-toolbar">
        <div className="catalog-filter-stack">
          <div className="category-pills" aria-label="Filter products by category">
            {categoryTypes.map((category) => (
              <button
                key={category}
                type="button"
                className={`category-pill${activeCategory === category ? ' category-pill--active' : ''}`}
                onClick={() => setActiveCategory(category)}
              >
                {category}
              </button>
            ))}
          </div>

          <div className="subcategory-pills" aria-label="Filter products by drink type">
            {subcategoryTypes.map((subcategory) => (
              <button
                key={subcategory}
                type="button"
                className={`subcategory-pill${activeSubcategory === subcategory ? ' subcategory-pill--active' : ''}`}
                onClick={() => setActiveSubcategory(subcategory)}
              >
                {subcategory}
              </button>
            ))}
          </div>
        </div>

        <label className="search-field">
          <span>Search products</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by brand, drink type, category, size, or note"
          />
          <small>Try: Johnnie Walker, tequila, gin, cabernet, tonic, lager</small>
        </label>
      </div>

      <div className="search-meta">
        <span>
          Showing {filteredProducts.length} of {products.length} items
        </span>
        {query || activeSubcategory !== 'All' ? (
          <button
            type="button"
            className="ghost-button"
            onClick={() => {
              setQuery('');
              setActiveSubcategory('All');
            }}
          >
            Clear search
          </button>
        ) : null}
      </div>

      <div className="product-grid">
        {filteredProducts.map((product) => (
          <article key={product.id} className="product-card">
            <div className="product-visual">
              {product.image && !imageErrors[product.id] ? (
                <img
                  className="product-photo"
                  src={product.image}
                  alt={product.name}
                  loading="lazy"
                  onError={(event) => {
                    setImageErrors((current) => ({
                      ...current,
                      [product.id]: true,
                    }));
                  }}
                />
              ) : null}
              {(!product.image || imageErrors[product.id]) ? (
                <div className="product-photo-fallback" aria-hidden="true">
                  <div className="bottle-shape" />
                </div>
              ) : null}
              <div className="product-visual-badge" aria-hidden="true">{categoryEmblems[product.category] ?? 'L'}</div>
            </div>

            <p className="product-category">{product.category} · {product.subcategory} · {product.size}</p>
            <p className="product-brand">{product.brand}</p>
            <h3>{product.name}</h3>
            <p className="product-note">{product.note}</p>
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
