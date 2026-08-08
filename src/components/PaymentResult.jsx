import { useEffect, useMemo, useState } from 'react';

const DEFAULT_PRODUCTION_API_BASE_URL = 'https://onmac-store.onrender.com';

function resolveApiBaseUrl() {
  const configured = String(import.meta.env.VITE_API_BASE_URL || '').trim();
  if (configured) {
    return configured.replace(/\/$/, '');
  }

  if (import.meta.env.PROD) {
    return DEFAULT_PRODUCTION_API_BASE_URL;
  }

  return '';
}

const API_BASE_URL = resolveApiBaseUrl();

function apiUrl(path) {
  if (!API_BASE_URL) {
    return path;
  }
  return `${API_BASE_URL}${path}`;
}

export default function PaymentResult() {
  const params = useMemo(() => new URLSearchParams(window.location.search), []);
  const sessionId = params.get('session_id') || params.get('session') || '';

  const [statusPayload, setStatusPayload] = useState({
    payment_status: params.get('payment_status') || '',
    order_status: params.get('order_status') || '',
    order_reference: params.get('order_reference') || 'N/A',
    payment_reference: params.get('payment_reference') || 'N/A',
    order_tracking_id: params.get('order_tracking_id') || 'N/A',
  });
  const [loading, setLoading] = useState(Boolean(sessionId));

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    let isActive = true;

    async function verifyStripeSession() {
      try {
        const response = await fetch(
          apiUrl(`/api/payments/stripe/success/?session_id=${encodeURIComponent(sessionId)}&no_redirect=1`)
        );
        const data = await response.json();
        if (!isActive || !response.ok) {
          return;
        }

        setStatusPayload((current) => ({
          payment_status: data.payment_status || current.payment_status,
          order_status: data.order_status || current.order_status,
          order_reference: data.order_reference || current.order_reference,
          payment_reference: data.payment_reference || current.payment_reference,
          order_tracking_id: current.order_tracking_id,
        }));
      } catch {
        // Keep existing query-param state if verification request fails.
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    }

    verifyStripeSession();

    return () => {
      isActive = false;
    };
  }, [sessionId]);

  const paymentStatus = String(statusPayload.payment_status || '').toLowerCase();
  const orderStatus = String(statusPayload.order_status || '').toLowerCase();
  const orderReference = statusPayload.order_reference || 'N/A';
  const paymentReference = statusPayload.payment_reference || 'N/A';
  const orderTrackingId = statusPayload.order_tracking_id || 'N/A';

  const isSuccess = paymentStatus === 'completed' || paymentStatus === 'succeeded' || paymentStatus === 'paid' || orderStatus === 'paid' || orderStatus === 'completed';
  const isFailed = paymentStatus === 'failed' || orderStatus === 'failed' || paymentStatus === 'cancelled' || orderStatus === 'cancelled';

  const title = isSuccess
    ? 'Order received'
    : isFailed
      ? 'Payment not completed'
      : 'Payment is being confirmed';

  const message = isSuccess
    ? 'Your payment was received and your order has been confirmed. We will send you a confirmation shortly.'
    : isFailed
      ? 'Your payment did not complete. You can return to checkout and try again.'
      : loading
        ? 'Your payment is being verified. This usually takes a few seconds.'
        : 'We received your callback and are still confirming the final provider status.';

  return (
    <div className="app-shell">
      <main>
        <section className="payment-result-card">
          <p className="eyebrow">Payment Result</p>
          <h2>{title}</h2>
          <p>{message}</p>

          <div className="payment-result-grid">
            <p><strong>Order reference:</strong> {orderReference}</p>
            <p><strong>Payment reference:</strong> {paymentReference}</p>
            <p><strong>Tracking ID:</strong> {orderTrackingId}</p>
            <p><strong>Order status:</strong> {orderStatus || 'unknown'}</p>
            <p><strong>Payment status:</strong> {paymentStatus || 'unknown'}</p>
          </div>

          <a className="submit-button" href="/">Back to store</a>
        </section>
      </main>
    </div>
  );
}
