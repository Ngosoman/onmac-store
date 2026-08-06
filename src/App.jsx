import { useMemo, useState } from 'react';
import Header from './components/Header';
import ProductGrid from './components/ProductGrid';
import CartSection from './components/CartSection';
import CheckoutForm from './components/CheckoutForm';
import Footer from './components/Footer';
import PaymentResult from './components/PaymentResult';
import { products } from './data/products';

export default function App() {
  const [cart, setCart] = useState([]);
  const [cartFeedback, setCartFeedback] = useState(null);

  if (window.location.pathname.startsWith('/payment-result')) {
    return <PaymentResult />;
  }

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

      const nextCart = existingItem
        ? currentCart.map((item) =>
            item.id === product.id ? { ...item, quantity: item.quantity + 1 } : item,
          )
        : [...currentCart, { id: product.id, quantity: 1 }];

      const nextCount = nextCart.reduce((total, item) => total + item.quantity, 0);
      setCartFeedback({ productName: product.name, count: nextCount });

      window.clearTimeout(window.__cartFeedbackTimeout);
      window.__cartFeedbackTimeout = window.setTimeout(() => {
        setCartFeedback(null);
      }, 2400);

      return nextCart;
    });
  }

  function handleDecreaseItem(productId) {
    setCart((currentCart) =>
      currentCart
        .map((item) =>
          item.id === productId ? { ...item, quantity: item.quantity - 1 } : item,
        )
        .filter((item) => item.quantity > 0),
    );
  }

  function handleIncreaseItem(productId) {
    setCart((currentCart) =>
      currentCart.map((item) =>
        item.id === productId ? { ...item, quantity: item.quantity + 1 } : item,
      ),
    );
  }

  function handleRemoveItem(productId) {
    setCart((currentCart) => currentCart.filter((item) => item.id !== productId));
  }

  return (
    <div className="app-shell">
      {cartFeedback ? (
        <div className="cart-toast" role="status" aria-live="polite">
          <span>Added {cartFeedback.productName} to your cart.</span>
          <button
            type="button"
            className="ghost-button"
            onClick={() => document.getElementById('cart')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
          >
            View cart
          </button>
        </div>
      ) : null}
      <Header cartCount={cartCount} />
      <main>
        <ProductGrid onAddToCart={handleAddToCart} />
        <CartSection
          cartItems={cartItems}
          onIncreaseItem={handleIncreaseItem}
          onDecreaseItem={handleDecreaseItem}
          onRemoveItem={handleRemoveItem}
          onProceedToCheckout={() => document.getElementById('checkout')?.scrollIntoView({ behavior: 'smooth' })}
        />
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
