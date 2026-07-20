export default function PaymentResult() {
  const params = new URLSearchParams(window.location.search);
  const paymentStatus = (params.get('payment_status') || '').toLowerCase();
  const orderStatus = (params.get('order_status') || '').toLowerCase();
  const orderReference = params.get('order_reference') || 'N/A';
  const paymentReference = params.get('payment_reference') || 'N/A';
  const orderTrackingId = params.get('order_tracking_id') || 'N/A';

  const isSuccess = paymentStatus === 'completed' || orderStatus === 'paid';
  const isFailed = paymentStatus === 'failed' || orderStatus === 'failed' || paymentStatus === 'cancelled' || orderStatus === 'cancelled';

  const title = isSuccess
    ? 'Payment Successful'
    : isFailed
      ? 'Payment Not Completed'
      : 'Payment Is Processing';

  const message = isSuccess
    ? 'Your payment was received and your order is confirmed.'
    : isFailed
      ? 'Your payment did not complete. You can return and try checkout again.'
      : 'We received your callback and are still confirming final provider status.';

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
