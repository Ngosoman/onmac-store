import { useState } from 'react';

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

async function parseApiResponse(response) {
  const contentType = String(response.headers.get('content-type') || '').toLowerCase();
  if (contentType.includes('application/json')) {
    return response.json();
  }

  const text = await response.text();
  return { detail: [text || `Request failed with status ${response.status}.`] };
}

export default function ContactPage() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [statusType, setStatusType] = useState('idle');

  async function handleSubmit(event) {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setStatusMessage('');
    setStatusType('idle');

    const formData = new FormData(event.currentTarget);
    const payload = {
      name: String(formData.get('name') || '').trim(),
      email: String(formData.get('email') || '').trim(),
      phone: String(formData.get('phone') || '').trim(),
      subject: String(formData.get('subject') || '').trim(),
      message: String(formData.get('message') || '').trim(),
    };

    if (!payload.name || !payload.email || !payload.subject || !payload.message) {
      setStatusType('error');
      setStatusMessage('Please complete all required fields before sending your message.');
      setIsSubmitting(false);
      return;
    }

    try {
      const response = await fetch(apiUrl('/api/contact/'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await parseApiResponse(response);
      if (!response.ok) {
        throw new Error(data?.detail?.[0] || 'Unable to send message right now.');
      }

      setStatusType('success');
      setStatusMessage('Message sent. We will get back to you soon.');
      event.currentTarget.reset();
    } catch (error) {
      setStatusType('error');
      setStatusMessage(error instanceof Error ? error.message : 'Unable to send message right now.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="app-shell">
      <section className="contact-page">
        <div className="contact-intro">
          <p className="eyebrow">Contact Us</p>
          <h1>We are here to help with your order, delivery, or bulk requests</h1>
          <p>
            Reach us directly using the details below or send a message through the form.
            Your contact request is delivered to our team email.
          </p>
          <div className="contact-details">
            <a href="mailto:onmac.limited@gmail.com">onmac.limited@gmail.com</a>
            <a href="tel:+19046633995">+19046633995</a>
          </div>
          <a className="contact-back-link" href="/">Back to store</a>
        </div>

        <form className="contact-form" onSubmit={handleSubmit}>
          <label>
            Full name
            <input name="name" type="text" required />
          </label>

          <label>
            Email
            <input name="email" type="email" required />
          </label>

          <label>
            Phone
            <input name="phone" type="tel" placeholder="Optional" />
          </label>

          <label>
            Subject
            <input name="subject" type="text" required />
          </label>

          <label>
            Message
            <textarea name="message" rows="6" required />
          </label>

          {statusMessage ? (
            <p className={`contact-status contact-status--${statusType}`} role="status" aria-live="polite">
              {statusMessage}
            </p>
          ) : null}

          <button className="submit-button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Sending...' : 'Send message'}
          </button>
        </form>
      </section>
    </div>
  );
}