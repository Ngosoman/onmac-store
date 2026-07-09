import { useMemo, useState } from 'react';
import Header from './components/Header';
import Hero from './components/Hero';
import ProductGrid from './components/ProductGrid';
import CheckoutForm from './components/CheckoutForm';
import Footer from './components/Footer';
import { products } from './data/products';

export default function App() {
  const [cart, setCart] = useState([]);

  const cartCount = cart.reduce((total, item) => total + item.quantity, 0);

  const cartItems = useMemo(
    () =>
      cart.map((item) => {
        const product = products.find((entry) => entry.id === item.id);

        return {
          ...item,
          product,
        };
      }),
    [cart],
  );

  function handleAddToCart(product) {
    setCart((currentCart) => {
      const existingItem = currentCart.find((item) => item.id === product.id);

      if (existingItem) {
        return currentCart.map((item) =>
          item.id === product.id ? { ...item, quantity: item.quantity + 1 } : item,
        );
      }

      return [...currentCart, { id: product.id, quantity: 1 }];
    });
  }

  return (
    <div className="app-shell">
      <Header cartCount={cartCount} />
      <main>
        <Hero />
        <ProductGrid onAddToCart={handleAddToCart} />
        <section className="checkout-section" id="checkout">
          <div className="section-heading">
            <p className="eyebrow">Checkout</p>
            <h2>Fast, focused, and easy to scan</h2>
          </div>
          <CheckoutForm cartItems={cartItems} />
        </section>
      </main>
      <Footer />
    </div>
  );
}
