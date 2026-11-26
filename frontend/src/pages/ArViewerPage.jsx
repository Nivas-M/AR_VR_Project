import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import "@google/model-viewer";
import {
  ArrowLeft,
  CheckCircle2,
  Download,
  Lock,
  QrCode,
  Ruler,
  Smartphone,
} from "lucide-react";
import { formatDimensions, getModelGlbUrl, getModelMeta } from "../api/client";
import QrShareModal from "../components/QrShareModal";
import { convertGlbUrlToUsdzBlobUrl } from "../utils/usdzExport";

export default function ArViewerPage() {
  const { id } = useParams();
  const modelUrl = getModelGlbUrl(id);

  const [meta, setMeta] = useState(null);
  const [usdzUrl, setUsdzUrl] = useState("");
  const [usdzStatus, setUsdzStatus] = useState("preparing");
  const [qrOpen, setQrOpen] = useState(false);

  useEffect(() => {
    let active = true;
    getModelMeta(id)
      .then((data) => {
        if (active) setMeta(data);
      })
      .catch(() => {
        if (active) setMeta(null);
      });
    return () => {
      active = false;
    };
  }, [id]);

  useEffect(() => {
    let active = true;
    let createdUrl = "";

    setUsdzStatus("preparing");
    convertGlbUrlToUsdzBlobUrl(modelUrl)
      .then((blobUrl) => {
        if (!active) {
          URL.revokeObjectURL(blobUrl);
          return;
        }
        createdUrl = blobUrl;
        setUsdzUrl(blobUrl);
        setUsdzStatus("ready");
      })
      .catch(() => {
        if (active) setUsdzStatus("unavailable");
      });

    return () => {
      active = false;
      if (createdUrl) {
        URL.revokeObjectURL(createdUrl);
      }
    };
  }, [modelUrl]);

  const dims = formatDimensions(meta?.scale_report?.bounding_box_m);
  const title = meta?.title || `TrueScale Model (${id})`;

  return (
    <div className="ts-ar-layout">
      <div className="ts-ar-topbar">
        <Link to="/studio" className="ts-btn ts-btn-secondary">
          <ArrowLeft size={16} />
          <span>Back to Studio</span>
        </Link>

        <div className="ts-ar-badges">
          <span className="ts-lock-badge">
            <Lock size={14} /> 1:1 Scale Locked (Pinch-Resize Disabled)
          </span>
          {usdzStatus === "ready" && (
            <span className="ts-ios-badge">
              <CheckCircle2 size={14} /> iOS Quick Look USDZ Ready
            </span>
          )}
        </div>
      </div>

      <div className="ts-ar-grid">
        <div className="ts-page-card ts-ar-stage-card">
          <model-viewer
            src={modelUrl}
            ios-src={usdzUrl || undefined}
            alt={title}
            ar=""
            ar-scale="fixed"
            ar-modes="webxr scene-viewer quick-look"
            ar-placement="floor"
            camera-controls=""
            touch-action="pan-y"
            shadow-intensity="1"
            exposure="1"
            class="ts-model-viewer"
            data-testid="ar-model-viewer"
          >
            <button slot="ar-button" type="button" className="ts-ar-launch-btn">
              <Smartphone size={18} />
              <span>View in Your Room (1:1 True Scale)</span>
            </button>
          </model-viewer>
        </div>

        <aside className="ts-page-card ts-ar-sidebar">
          <span className="ts-eyebrow">WebAR True-Scale Handoff</span>
          <h1>{title}</h1>

          {dims ? (
            <div className="ts-ar-dims-box">
              <div className="ts-section-title">
                <Ruler size={17} />
                <h2>Physical Footprint</h2>
              </div>
              <p className="ts-ar-dim-primary">{dims.cmLabel}</p>
              <p className="ts-muted">{dims.inLabel}</p>
              <p className="ts-muted">{dims.mLabel} (glTF meter scale)</p>
            </div>
          ) : (
            <p className="ts-muted">
              Model <code>{id}</code> loaded at <code>1 unit = 1 meter</code>, grounded on the floor
              plane (<code>Y = 0</code>).
            </p>
          )}

          <div className="ts-ar-actions">
            <button
              type="button"
              className="ts-btn ts-btn-primary ts-btn-full"
              onClick={() => setQrOpen(true)}
            >
              <QrCode size={18} />
              <span>Scan QR to Place from Phone</span>
            </button>

            <a href={modelUrl} download={`${id}.glb`} className="ts-btn ts-btn-secondary ts-btn-full">
              <Download size={16} />
              <span>Download Metric .glb (Android / WebXR)</span>
            </a>

            {usdzUrl && (
              <a
                href={usdzUrl}
                download={`${id}.usdz`}
                rel="ar"
                className="ts-btn ts-btn-amazon ts-btn-full"
              >
                <Download size={16} />
                <span>Download / Launch .usdz (iOS Quick Look)</span>
              </a>
            )}
          </div>

          <div className="ts-ar-notes">
            <h3>AR Compatibility</h3>
            <ul>
              <li>
                <strong>Android:</strong> Chrome WebXR or Google Scene Viewer (uses <code>.glb</code>{" "}
                with <code>ar-scale=&quot;fixed&quot;</code>).
              </li>
              <li>
                <strong>iPhone / iPad:</strong> Safari Apple AR Quick Look (browser-generated{" "}
                <code>.usdz</code> from the scaled <code>.glb</code>).
              </li>
              <li>
                <strong>Note:</strong> Mobile camera AR requires HTTPS (or <code>localhost</code>). Use
                the QR dialog to paste a Cloudflare/ngrok HTTPS tunnel URL if testing from a phone.
              </li>
            </ul>
          </div>
        </aside>
      </div>

      <QrShareModal open={qrOpen} onClose={() => setQrOpen(false)} modelTitle={title} />
    </div>
  );
}
