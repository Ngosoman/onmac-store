export default function Hero() {
  return (
    <section className="hero">
      <div className="hero-copy">
        <p className="eyebrow">Curated selection</p>
        <h2>A cleaner storefront for browsing, picking, and checking out.</h2>
        <p>
          Built as a React JSX storefront with separated components, a small data layer,
          and a checkout flow you can extend as the project grows.
        </p>
      </div>
      <div className="hero-card">
        <span>New arrivals</span>
        <strong>Seasonal picks</strong>
        <p>Featured products, streamlined layout, and room for future catalog data.</p>
      </div>
    </section>
  );
}
