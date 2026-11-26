import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { Check, Copy, Smartphone, X } from "lucide-react";

export default function QrShareModal({ open, onClose, modelTitle }) {
  const [shareUrl, setShareUrl] = useState(() =>
    typeof window !== "undefined" ? window.location.href : ""
  );
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (open && typeof window !== "undefined") {
      setShareUrl(window.location.href);
    }
  }, [open]);

  if (!open) return null;

  const isLocalhost = /localhost|127\.0\.0\.1/.test(shareUrl);

  const handleCopy = async () => {
    try {
      await navigator.clipboard?.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard API unavailable in non-HTTPS or test environments.
    }
  };

  return (
    <div className="ts-modal-backdrop" role="dialog" aria-modal="true" aria-label="QR Code Phone Handoff">
      <div className="ts-modal-card">
        <div className="ts-modal-head">
          <div className="ts-modal-title">
            <Smartphone size={20} />
            <h3>Open on Your Phone for Room AR</h3>
          </div>
          <button type="button" className="ts-icon-btn" onClick={onClose} aria-label="Close QR modal">
            <X size={18} />
          </button>
        </div>

        <p className="ts-muted">
          Scan with your Android or iPhone camera to place <strong>{modelTitle || "this item"}</strong>{" "}
          in your room at locked <code>1:1</code> real-world scale.
        </p>

        <div className="ts-qr-box">
          <QRCodeSVG value={shareUrl || "https://localhost"} size={200} level="M" includeMargin />
        </div>

        {isLocalhost && (
          <div className="ts-alert ts-alert-warn">
            <code>localhost</code> cannot be reached from a phone. Replace it below with your PC&apos;s
            LAN IP (e.g. <code>http://192.168.1.42:5173/...</code>) or an HTTPS tunnel URL.
          </div>
        )}

        <label className="ts-field">
          <span>Mobile-Accessible AR URL</span>
          <div className="ts-copy-row">
            <input
              type="url"
              value={shareUrl}
              onChange={(e) => setShareUrl(e.target.value)}
              aria-label="Mobile AR URL"
            />
            <button type="button" className="ts-btn ts-btn-secondary" onClick={handleCopy}>
              {copied ? <Check size={15} /> : <Copy size={15} />}
              <span>{copied ? "Copied" : "Copy"}</span>
            </button>
          </div>
        </label>
      </div>
    </div>
  );
}
