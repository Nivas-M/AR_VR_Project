import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Box, CheckCircle2, Ruler, Search, Sparkles, Star } from "lucide-react";
import { listProducts } from "../api/client";

export default function StorefrontPage() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");

  useEffect(() => {
    let active = true;
    setLoading(true);
    listProducts()
      .then((data) => {
        if (active) {
          setProducts(Array.isArray(data?.products) ? data.products : []);
          setError("");
        }
      })
      .catch((err) => {
        if (active) setError(err?.message || "Failed to load catalog products");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const categories = useMemo(() => {
    const unique = Array.from(new Set(products.map((p) => p.category).filter(Boolean)));
    return ["All", ...unique];
  }, [products]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return products.filter((p) => {
      const catMatch = category === "All" || p.category === category;
      if (!catMatch) return false;
      if (!q) return true;
      return (
        p.title.toLowerCase().includes(q) ||
        p.brand.toLowerCase().includes(q) ||
        p.category.toLowerCase().includes(q) ||
        p.description.toLowerCase().includes(q)
      );
    });
  }, [products, query, category]);

  return (
    <div className="ts-store-layout">
      <section className="ts-store-hero">
        <div className="ts-store-hero-content">
          <span className="ts-amazon-badge">ShopScale Demo Storefront</span>
          <h1>Shop Furniture &amp; Home Gear at Verified 1:1 Room Scale</h1>
          <p>
            Every listing below uses real multi-angle photos and physical dimensions to generate a
            locked <code>1:1</code> metric 3D model on your local PC—ready to place in your room.
          </p>
        </div>
        <div className="ts-store-hero-cta">
          <Link to="/studio" className="ts-btn ts-btn-amazon">
            <Sparkles size={16} />
            <span>Try With Your Own Photos</span>
          </Link>
        </div>
      </section>

      <section className="ts-store-controls">
        <div className="ts-search-box">
          <Search size={18} className="ts-muted" />
          <input
            type="search"
            placeholder="Search armchairs, tables, lamps, speakers..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search ShopScale products"
          />
        </div>

        <div className="ts-chip-wrap" role="group" aria-label="Filter by category">
          {categories.map((cat) => (
            <button
              key={cat}
              type="button"
              className={`ts-chip ${category === cat ? "active" : ""}`}
              onClick={() => setCategory(cat)}
            >
              {cat}
            </button>
          ))}
        </div>
      </section>

      {error && (
        <div className="ts-alert ts-alert-error" role="alert">
          {error}
        </div>
      )}

      {loading ? (
        <div className="ts-page-card">Loading ShopScale catalog...</div>
      ) : filtered.length === 0 ? (
        <div className="ts-page-card">
          <h3>No matching products</h3>
          <p className="ts-muted">Try clearing your search filter or upload custom photos in Studio.</p>
        </div>
      ) : (
        <div className="ts-product-grid">
          {filtered.map((product) => {
            const frontImg = product.images?.[0]?.url;
            return (
              <article key={product.id} className="ts-product-card">
                <Link to={`/product/${product.id}`} className="ts-product-img-wrap">
                  {frontImg ? (
                    <img src={frontImg} alt={product.title} className="ts-product-img" />
                  ) : (
                    <Box size={40} className="ts-muted" />
                  )}
                  <span className="ts-ar-pill">
                    <CheckCircle2 size={12} /> 1:1 AR Ready
                  </span>
                </Link>

                <div className="ts-product-body">
                  <span className="ts-product-brand">
                    {product.brand} • {product.category}
                  </span>
                  <Link to={`/product/${product.id}`} className="ts-product-title">
                    {product.title}
                  </Link>

                  <div className="ts-rating-row">
                    <Star size={14} fill="#f59e0b" color="#f59e0b" />
                    <strong>{product.rating}</strong>
                    <span className="ts-muted">({product.review_count?.toLocaleString()})</span>
                  </div>

                  <div className="ts-price-row">
                    <span className="ts-price">${Number(product.price_usd).toFixed(2)}</span>
                    <span className="ts-dim-tag">
                      <Ruler size={13} />
                      {product.width_cm} × {product.height_cm} × {product.depth_cm} cm
                    </span>
                  </div>

                  <div className="ts-product-actions">
                    <Link to={`/product/${product.id}`} className="ts-btn ts-btn-amazon ts-btn-full">
                      View Listing &amp; True-Scale AR
                    </Link>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
