import { products } from '../data/products';

export default function ProductGrid({ onAddToCart }) {
  return (
    <section className="products-section" id="products">
      <div className="section-heading">
        <p className="eyebrow">Featured</p>
        <h2>Products</h2>
      </div>
      <div className="product-grid">
        {products.map((product) => (
          <article key={product.id} className="product-card">
            <p className="product-category">{product.category}</p>
            <h3>{product.name}</h3>
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
    </section>
  );
}
