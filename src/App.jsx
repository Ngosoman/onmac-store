import Header from './components/Header';
import Hero from './components/Hero';
import ProductGrid from './components/ProductGrid';
import CheckoutForm from './components/CheckoutForm';
import Footer from './components/Footer';

export default function App() {
  return (
    <div className="app-shell">
      <Header />
      <main>
        <Hero />
        <ProductGrid />
        <section className="checkout-section" id="checkout">
          <div className="section-heading">
            <p className="eyebrow">Checkout</p>
            <h2>Fast, focused, and easy to scan</h2>
          </div>
          <CheckoutForm />
        </section>
      </main>
      <Footer />
    </div>
  );
}
