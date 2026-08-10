import onmacLogo from '../assets/onmac-logo.png';

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-brand">
        <img className="footer-logo" src={onmacLogo} alt="Onmac logo" />
        <p>Onmac Liquor Store</p>
      </div>
      <a href="mailto:onmac.limited@gmail.com">onmac.limited@gmail.com</a>
      <a href="tel:+19046633995">+19046633995</a>
    </footer>
  );
}
