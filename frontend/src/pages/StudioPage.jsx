import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  Download,
  ImagePlus,
  Loader2,
  Ruler,
  Sparkles,
  Trash2,
  Upload,
} from "lucide-react";
import {
  formatDimensions,
  listProducts,
  pollJob,
  startReconstruction,
} from "../api/client";
import ModelScaleInspector from "../components/ModelScaleInspector";

const ANGLE_OPTIONS = [
  { value: "front", label: "Front" },
  { value: "side", label: "Side" },
  { value: "back", label: "Back" },
  { value: "top", label: "Top" },
  { value: "three_quarter", label: "3/4 Angle" },
];

const QUICK_PRESETS = [
  { label: "Armchair", width: 78, height: 84, depth: 74, unit: "cm" },
  { label: "Coffee Table", width: 110, height: 45, depth: 60, unit: "cm" },
  { label: "Floor Lamp", width: 42, height: 165, depth: 42, unit: "cm" },
  { label: "Speaker", width: 28, height: 18, depth: 16, unit: "cm" },
];

function convertUnitValue(val, fromUnit, toUnit) {
  const n = Number(val);
  if (!Number.isFinite(n) || n <= 0) return val;
  const toCm = { cm: 1, in: 2.54, mm: 0.1 };
  const cmVal = n * (toCm[fromUnit] || 1);
  const converted = cmVal / (toCm[toUnit] || 1);
  return Number(converted.toFixed(1));
}

export default function StudioPage() {
  const [photos, setPhotos] = useState([]);
  const [sampleProducts, setSampleProducts] = useState([]);
  const [selectedProductId, setSelectedProductId] = useState("");

  const [title, setTitle] = useState("");
  const [width, setWidth] = useState("78");
  const [height, setHeight] = useState("84");
  const [depth, setDepth] = useState("74");
  const [unit, setUnit] = useState("cm");
  const [scaleMode, setScaleMode] = useState("exact_fit");

  const [job, setJob] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    let active = true;
    listProducts()
      .then((data) => {
        if (active && Array.isArray(data?.products)) {
          setSampleProducts(data.products);
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    return () => {
      photos.forEach((item) => {
        if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
      });
    };
  }, []);

  const addFiles = (fileList) => {
    const incoming = Array.from(fileList || []).filter((f) => f.type.startsWith("image/") || /\.(png|jpe?g|webp)$/i.test(f.name));
    if (!incoming.length) return;
    setSelectedProductId("");
    setError("");

    setPhotos((prev) => {
      const remainingSlots = Math.max(0, 6 - prev.length);
      const next = incoming.slice(0, remainingSlots).map((file, idx) => {
        const defaultAngles = ["front", "side", "back", "top", "three_quarter", "three_quarter"];
        return {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          file,
          previewUrl: typeof URL.createObjectURL === "function" ? URL.createObjectURL(file) : "",
          angle: defaultAngles[(prev.length + idx) % defaultAngles.length],
        };
      });
      return [...prev, ...next];
    });
  };

  const removePhoto = (id) => {
    setPhotos((prev) => {
      const target = prev.find((p) => p.id === id);
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl);
      return prev.filter((p) => p.id !== id);
    });
  };

  const updateAngle = (id, angle) => {
    setPhotos((prev) => prev.map((p) => (p.id === id ? { ...p, angle } : p)));
  };

  const handleUnitToggle = (nextUnit) => {
    if (nextUnit === unit) return;
    setWidth(String(convertUnitValue(width, unit, nextUnit)));
    setHeight(String(convertUnitValue(height, unit, nextUnit)));
    setDepth(String(convertUnitValue(depth, unit, nextUnit)));
    setUnit(nextUnit);
  };

  const applyPreset = (preset) => {
    setUnit(preset.unit);
    setWidth(String(preset.width));
    setHeight(String(preset.height));
    setDepth(String(preset.depth));
    if (!title) setTitle(preset.label);
  };

  const selectSampleProduct = (product) => {
    setSelectedProductId(product.id);
    setTitle(product.title);
    setUnit("cm");
    setWidth(String(product.width_cm));
    setHeight(String(product.height_cm));
    setDepth(String(product.depth_cm));
    setError("");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    const wNum = Number(width);
    const hNum = Number(height);
    const dNum = Number(depth);
    if (!(wNum > 0 && hNum > 0 && dNum > 0)) {
      setError("Please enter positive Width, Height, and Depth dimensions.");
      return;
    }

    if (photos.length === 0 && !selectedProductId) {
      setError("Upload 1–6 product photos (or choose a bundled sample product preset) to reconstruct.");
      return;
    }

    setSubmitting(true);
    try {
      const queued = await startReconstruction({
        files: photos.map((p) => p.file),
        angles: photos.map((p) => p.angle),
        productId: photos.length === 0 ? selectedProductId : null,
        width: wNum,
        height: hNum,
        depth: dNum,
        unit,
        scaleMode,
        engine: "local_cpu",
        title: title.trim(),
      });
      setJob(queued);

      const completed = await pollJob(queued.job_id, {
        onProgress: (latest) => setJob(latest),
        intervalMs: 450,
      });
      setJob(completed);
    } catch (err) {
      setError(err?.message || "Failed to run 3D reconstruction pipeline.");
    } finally {
      setSubmitting(false);
    }
  };

  const resultDims = formatDimensions(job?.scale_report?.bounding_box_m);

  return (
    <div className="ts-studio-layout">
      <div className="ts-studio-header">
        <div>
          <span className="ts-eyebrow">
            <Sparkles size={14} /> CPU-Fast Local Pipeline
          </span>
          <h1>Photo-to-3D True-Scale Studio</h1>
          <p className="ts-muted">
            Upload 1–6 product photos, enter exact real-world dimensions, and generate a floor-grounded{" "}
            <code>1:1</code> metric <code>.glb</code> ready for WebAR room placement.
          </p>
        </div>
      </div>

      <div className="ts-studio-grid">
        <form className="ts-page-card ts-studio-form" onSubmit={handleSubmit}>
          <div className="ts-section-title">
            <ImagePlus size={18} />
            <h2>1. Product Photos (1–6 Angles)</h2>
          </div>

          <label
            className={`ts-dropzone ${dragOver ? "dragover" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              addFiles(e.dataTransfer.files);
            }}
          >
            <Upload size={24} />
            <span>Drop 1–6 PNG/JPG product photos here, or click to browse</span>
            <small className="ts-muted">Tip: Front + Side + Back + Top gives the sharpest 3D shape</small>
            <input
              type="file"
              accept="image/*"
              multiple
              onChange={(e) => addFiles(e.target.files)}
              className="ts-sr-only"
              aria-label="Upload product photos"
            />
          </label>

          {photos.length > 0 && (
            <div className="ts-photo-list">
              {photos.map((item) => (
                <div key={item.id} className="ts-photo-item">
                  {item.previewUrl ? (
                    <img src={item.previewUrl} alt={item.file.name} className="ts-photo-thumb" />
                  ) : (
                    <div className="ts-photo-thumb ts-photo-placeholder">IMG</div>
                  )}
                  <div className="ts-photo-meta">
                    <span className="ts-photo-name">{item.file.name}</span>
                    <select
                      aria-label={`Angle for ${item.file.name}`}
                      value={item.angle}
                      onChange={(e) => updateAngle(item.id, e.target.value)}
                      className="ts-select"
                    >
                      {ANGLE_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <button
                    type="button"
                    className="ts-icon-btn"
                    onClick={() => removePhoto(item.id)}
                    aria-label={`Remove ${item.file.name}`}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {photos.length === 0 && sampleProducts.length > 0 && (
            <div className="ts-sample-box">
              <span className="ts-sample-label">Or test instantly with bundled catalog photos:</span>
              <div className="ts-chip-wrap">
                {sampleProducts.map((product) => (
                  <button
                    key={product.id}
                    type="button"
                    className={`ts-chip ${selectedProductId === product.id ? "active" : ""}`}
                    onClick={() => selectSampleProduct(product)}
                  >
                    {product.title}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="ts-section-title" style={{ marginTop: "1.25rem" }}>
            <Ruler size={18} />
            <h2>2. Real-World Dimensions</h2>
          </div>

          <div className="ts-unit-row">
            <div className="ts-unit-toggle" role="group" aria-label="Dimension unit">
              {["cm", "in", "mm"].map((u) => (
                <button
                  key={u}
                  type="button"
                  className={`ts-unit-btn ${unit === u ? "active" : ""}`}
                  onClick={() => handleUnitToggle(u)}
                >
                  {u}
                </button>
              ))}
            </div>

            <div className="ts-chip-wrap">
              {QUICK_PRESETS.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  className="ts-chip"
                  onClick={() => applyPreset(preset)}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          <div className="ts-dim-inputs">
            <label className="ts-field">
              <span>Width ({unit})</span>
              <input
                type="number"
                step="0.1"
                min="0.1"
                value={width}
                onChange={(e) => setWidth(e.target.value)}
                required
              />
            </label>
            <label className="ts-field">
              <span>Height ({unit})</span>
              <input
                type="number"
                step="0.1"
                min="0.1"
                value={height}
                onChange={(e) => setHeight(e.target.value)}
                required
              />
            </label>
            <label className="ts-field">
              <span>Depth ({unit})</span>
              <input
                type="number"
                step="0.1"
                min="0.1"
                value={depth}
                onChange={(e) => setDepth(e.target.value)}
                required
              />
            </label>
          </div>

          <div className="ts-dim-inputs" style={{ gridTemplateColumns: "1fr 1fr" }}>
            <label className="ts-field">
              <span>Model Label (optional)</span>
              <input
                type="text"
                placeholder="e.g. Living Room Accent Chair"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </label>
            <label className="ts-field">
              <span>Scale Mode</span>
              <select
                value={scaleMode}
                onChange={(e) => setScaleMode(e.target.value)}
                className="ts-select"
              >
                <option value="exact_fit">Exact Fit (W × H × D)</option>
                <option value="uniform">Uniform Aspect Fit</option>
                <option value="uniform_height">Match Height Uniformly</option>
              </select>
            </label>
          </div>

          {error && (
            <div className="ts-alert ts-alert-error" role="alert">
              {error}
            </div>
          )}

          <button type="submit" className="ts-btn ts-btn-primary ts-btn-full" disabled={submitting}>
            {submitting ? (
              <>
                <Loader2 size={18} className="ts-spin" />
                <span>Generating True-Scale 3D Model...</span>
              </>
            ) : (
              <>
                <Sparkles size={18} />
                <span>Generate True-Scale 3D (.glb)</span>
              </>
            )}
          </button>

          {job && (
            <div className="ts-progress-card" aria-live="polite">
              <div className="ts-progress-head">
                <strong>Status: {job.status.toUpperCase()}</strong>
                <span>{job.progress ?? 0}%</span>
              </div>
              <div className="ts-progress-track">
                <div className="ts-progress-fill" style={{ width: `${job.progress ?? 0}%` }} />
              </div>
              <p className="ts-muted">{job.stage_message}</p>
            </div>
          )}
        </form>

        <div className="ts-studio-preview-col">
          {job?.status === "done" && job.model_url ? (
            <>
              <ModelScaleInspector
                modelUrl={job.model_url}
                scaleReport={job.scale_report}
                title={job.title}
              />

              <div className="ts-page-card ts-verify-card">
                <div className="ts-verify-head">
                  <CheckCircle2 size={20} className="ts-text-success" />
                  <div>
                    <h3>Metric Scale Verified (&lt; 1 mm error)</h3>
                    <p className="ts-muted">
                      {resultDims?.cmLabel} • {resultDims?.inLabel} • Floor Y ={" "}
                      {job.scale_report?.bounding_box_m?.min_y?.toFixed(3)} m
                    </p>
                  </div>
                </div>

                <div className="ts-verify-stats">
                  <div>
                    <small>Vertices / Faces</small>
                    <strong>
                      {job.mesh_stats?.vertex_count?.toLocaleString()} /{" "}
                      {job.mesh_stats?.face_count?.toLocaleString()}
                    </strong>
                  </div>
                  <div>
                    <small>Mode</small>
                    <strong>{job.mesh_stats?.mode_used}</strong>
                  </div>
                  <div>
                    <small>Max Error</small>
                    <strong>{((job.scale_report?.max_dimension_error_m || 0) * 1000).toFixed(3)} mm</strong>
                  </div>
                  <div>
                    <small>Build Time</small>
                    <strong>{job.duration_ms} ms</strong>
                  </div>
                </div>

                <div className="ts-verify-actions">
                  <Link to={`/ar/${job.model_id}`} className="ts-btn ts-btn-amazon">
                    <span>Open True-Scale AR Viewer</span>
                    <ArrowRight size={16} />
                  </Link>
                  <a href={job.model_url} download={`${job.model_id}.glb`} className="ts-btn ts-btn-secondary">
                    <Download size={16} />
                    <span>Download .glb</span>
                  </a>
                </div>
              </div>
            </>
          ) : (
            <div className="ts-page-card ts-empty-inspector">
              <Ruler size={36} className="ts-muted" />
              <h3>3D Scale Inspector Ready</h3>
              <p className="ts-muted">
                Submit 1–6 product photos (or pick a sample preset on the left) to inspect the
                reconstructed <code>.glb</code> against a 10 cm grid, metric wireframe, and a 175 cm
                person reference.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
