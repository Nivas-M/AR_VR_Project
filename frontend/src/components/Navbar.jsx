import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { Box, ShoppingBag, Sparkles } from "lucide-react";
import { getHealth } from "../api/client";

export default function Navbar() {
  const [health, setHealth] = useState({ status: "checking", engine: "local_cpu" });

  useEffect(() => {
    let active = true;
    getHealth()
      .then((data) => {
        if (active) {
          setHealth({
            status: data.status === "ok" ? "online" : "degraded",
            engine: data.default_engine || "local_cpu",
          });
        }
      })
      .catch(() => {
        if (active) {
          setHealth({ status: "offline", engine: "local_cpu" });
        }
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <header className="ts-navbar">
      <div className="ts-navbar-inner">
        <NavLink to="/" className="ts-brand">
          <span className="ts-brand-icon">
            <Box size={20} />
          </span>
          <span className="ts-brand-text">
            <strong>TrueScale</strong>
            <span className="ts-brand-sub">1:1 Photo-to-3D &amp; WebAR</span>
          </span>
        </NavLink>

        <nav className="ts-nav-links" aria-label="Primary navigation">
          <NavLink
            to="/"
            end
            className={({ isActive }) => `ts-nav-link ${isActive ? "active" : ""}`}
          >
            <ShoppingBag size={16} />
            <span>ShopScale Storefront</span>
          </NavLink>
          <NavLink
            to="/studio"
            className={({ isActive }) => `ts-nav-link ${isActive ? "active" : ""}`}
          >
            <Sparkles size={16} />
            <span>Photo-to-3D Studio</span>
          </NavLink>
        </nav>

        <div className="ts-status-pill" title={`Engine: ${health.engine}`}>
          <span className={`ts-status-dot ${health.status}`} />
          <span>
            {health.status === "online"
              ? `API Ready (${health.engine})`
              : health.status === "checking"
                ? "Checking API..."
                : "API Offline"}
          </span>
        </div>
      </div>
    </header>
  );
}
