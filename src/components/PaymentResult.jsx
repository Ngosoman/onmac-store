export default function PaymentResult() {
  const params = new URLSearchParams(window.location.search);
  const paymentStatus = (params.get('payment_status') || '').toLowerCase();
  const orderStatus = (params.get('order_status') || '').toLowerCase();
  const orderReference = params.get('order_reference') || 'N/A';
  const paymentReference = params.get('payment_reference') || 'N/A';
  const orderTrackingId = params.get('order_tracking_id') || 'N/A';

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
