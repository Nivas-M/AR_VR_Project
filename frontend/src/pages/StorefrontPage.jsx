import { Link } from "react-router-dom";

export default function StorefrontPage() {
  return (
    <section className="ts-page-card">
      <h1>ShopScale Demo Storefront</h1>
      <p>Mock Amazon-style storefront loading catalog items and true-scale AR handoff.</p>
      <Link to="/studio" className="ts-btn ts-btn-primary">
        Open Photo-to-3D Studio
      </Link>
    </section>
  );
}
