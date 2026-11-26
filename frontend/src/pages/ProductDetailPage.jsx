import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  Box,
  CheckCircle2,
  Loader2,
  Ruler,
  ShieldCheck,
  Smartphone,
  Sparkles,
  Star,
} from "lucide-react";
import { getProduct, pollJob, startReconstruction } from "../api/client";
import ModelScaleInspector from "../components/ModelScaleInspector";

export default function ProductDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeImageIdx, setActiveImageIdx] = useState(0);

  const [job, setJob] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [pipelineError, setPipelineError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setActiveImageIdx(0);
    setJob(null);
    setPipelineError("");

    getProduct(id)
      .then((data) => {
        if (active) {
          setProduct(data);
          setError("");
        }
      })
      .catch((err) => {
        if (active) setError(err?.message || "Product not found");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [id]);

  const runPipeline = async ({ openArAfter = false } = {}) => {
    if (!product) return;
    if (openArAfter && job?.status === "done" && job.model_id) {
      navigate(`/ar/${job.model_id}`);
      return;
    }

    setGenerating(true);
    setPipelineError("");
    try {
      const queued = await startReconstruction({
        productId: product.id,
        width: product.width_cm,
        height: product.height_cm,
        depth: product.depth_cm,
        unit: "cm",
        scaleMode: "exact_fit",
        engine: "local_cpu",
        title: product.title,
      });
      setJob(queued);

      const completed = await pollJob(queued.job_id, {
        onProgress: (latest) => setJob(latest),
        intervalMs: 400,
      });
      setJob(completed);

      if (openArAfter && completed.model_id) {
        navigate(`/ar/${completed.model_id}`);
      }
    } catch (err) {
      setPipelineError(err?.message || "Failed to generate 3D model from listing photos");
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return <div className="ts-page-card">Loading product details...</div>;
  }

  if (error || !product) {
    return (
      <div className="ts-page-card">
        <h2>Product Unavailable</h2>
        <p className="ts-muted">{error || "Could not locate product."}</p>
        <Link to="/" className="ts-btn ts-btn-secondary">
          <ArrowLeft size={16} /> Back to ShopScale
        </Link>
      </div>
    );
  }

  const images = product.images || [];
  const activeImage = images[activeImageIdx] || images[0];

  return (
    <div className="ts-pdp-layout">
      <div className="ts-pdp-breadcrumb">
        <Link to="/" className="ts-link-inline">
          <ArrowLeft size={15} /> Back to ShopScale
        </Link>
        <span className="ts-muted">
          / {product.category} / {product.title}
        </span>
      </div>

      <div className="ts-pdp-grid">
        <div className="ts-page-card ts-gallery-card">
          <div className="ts-gallery-thumbs" role="tablist" aria-label="Product photo angles">
            {images.map((img, idx) => (
              <button
                key={img.filename}
                type="button"
                role="tab"
                aria-selected={idx === activeImageIdx}
                className={`ts-thumb-btn ${idx === activeImageIdx ? "active" : ""}`}
                onClick={() => setActiveImageIdx(idx)}
              >
                <img src={img.url} alt={`${product.title} - ${img.label}`} />
                <span>{img.label}</span>
              </button>
            ))}
          </div>

          <div className="ts-gallery-hero">
            {activeImage ? (
              <img
                src={activeImage.url}
                alt={`${product.title} ${activeImage.label}`}
                className="ts-gallery-main-img"
              />
            ) : (
              <Box size={48} className="ts-muted" />
            )}
            <span className="ts-gallery-angle-pill">{activeImage?.label || "Front View"}</span>
          </div>
        </div>

        <div className="ts-page-card ts-buybox">
          <span className="ts-product-brand">
            Brand: {product.brand} • {product.category}
          </span>
          <h1 className="ts-pdp-title">{product.title}</h1>

          <div className="ts-rating-row">
            <Star size={16} fill="#f59e0b" color="#f59e0b" />
            <strong>{product.rating}</strong>
            <span className="ts-muted">({product.review_count?.toLocaleString()} ratings)</span>
          </div>

          <div className="ts-pdp-price-block">
            <span className="ts-pdp-price">${Number(product.price_usd).toFixed(2)}</span>
            <span className="ts-stock-badge">In Stock • Free Local AR Preview</span>
          </div>

          <p className="ts-pdp-desc">{product.description}</p>

          <ul className="ts-pdp-highlights">
            {(product.highlights || []).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>

          <div className="ts-pdp-ar-cta-box">
            <div className="ts-pdp-ar-head">
              <Ruler size={18} />
              <div>
                <strong>
                  Exact Dimensions: {product.width_cm} × {product.height_cm} × {product.depth_cm} cm
                </strong>
                <span className="ts-muted">
                  ({product.dimensions_in?.width} × {product.dimensions_in?.height} ×{" "}
                  {product.dimensions_in?.depth} in)
                </span>
              </div>
            </div>

            <div className="ts-pdp-cta-buttons">
              <button
                type="button"
                className="ts-btn ts-btn-amazon ts-btn-full"
                onClick={() => runPipeline({ openArAfter: true })}
                disabled={generating}
              >
                {generating ? (
                  <>
                    <Loader2 size={17} className="ts-spin" />
                    <span>Building 1:1 3D Model for AR...</span>
                  </>
                ) : (
                  <>
                    <Smartphone size={17} />
                    <span>View in Your Room (True-Scale AR)</span>
                  </>
                )}
              </button>

              <button
                type="button"
                className="ts-btn ts-btn-primary ts-btn-full"
                onClick={() => runPipeline({ openArAfter: false })}
                disabled={generating}
              >
                <Sparkles size={17} />
                <span>Generate 3D from Listing Photos</span>
              </button>
            </div>

            {job && (
              <div className="ts-progress-card" aria-live="polite">
                <div className="ts-progress-head">
                  <strong>{job.status.toUpperCase()}</strong>
                  <span>{job.progress ?? 0}%</span>
                </div>
                <div className="ts-progress-track">
                  <div className="ts-progress-fill" style={{ width: `${job.progress ?? 0}%` }} />
                </div>
                <p className="ts-muted">{job.stage_message}</p>
              </div>
            )}

            {pipelineError && (
              <div className="ts-alert ts-alert-error" role="alert">
                {pipelineError}
              </div>
            )}

            {job?.status === "done" && job.model_id && (
              <div className="ts-pdp-ready-bar">
                <CheckCircle2 size={18} className="ts-text-success" />
                <span>3D `.glb` generated at 1:1 metric scale!</span>
                <Link to={`/ar/${job.model_id}`} className="ts-btn ts-btn-secondary">
                  Launch AR Viewer <ArrowRight size={15} />
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>

      {job?.status === "done" && job.model_url && (
        <section>
          <ModelScaleInspector
            modelUrl={job.model_url}
            scaleReport={job.scale_report}
            title={`${product.title} — Live Reconstructed 3D`}
          />
        </section>
      )}

      <section className="ts-page-card">
        <div className="ts-section-title">
          <ShieldCheck size={18} />
          <h2>Product Specifications &amp; Dimensions</h2>
        </div>

        <table className="ts-spec-table">
          <tbody>
            <tr>
              <th>Product Dimensions (cm)</th>
              <td>
                {product.width_cm} cm (W) × {product.height_cm} cm (H) × {product.depth_cm} cm (D)
              </td>
            </tr>
            <tr>
              <th>Product Dimensions (inches)</th>
              <td>
                {product.dimensions_in?.width} in (W) × {product.dimensions_in?.height} in (H) ×{" "}
                {product.dimensions_in?.depth} in (D)
              </td>
            </tr>
            <tr>
              <th>Metric AR Scale</th>
              <td>1.0 glTF unit = 1.0 meter (Floor grounded at Y = 0.000 m, pinch-resize locked)</td>
            </tr>
            <tr>
              <th>Material</th>
              <td>{product.material}</td>
            </tr>
            <tr>
              <th>Color / Finish</th>
              <td>{product.color}</td>
            </tr>
            <tr>
              <th>Item Weight</th>
              <td>{product.weight_kg} kg</td>
            </tr>
            <tr>
              <th>Listing Photo Angles</th>
              <td>{images.map((img) => img.label).join(", ")}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  );
}
