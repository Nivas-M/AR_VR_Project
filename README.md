# TrueScale AR — Photo-to-True-Scale 3D & ShopScale WebAR Demo

**TrueScale AR** converts 1–6 standard product photos and real-world dimensions (`Width × Height × Depth`) into a floor-grounded, **1:1 metric `.glb` 3D model** (`1.0 glTF unit = 1.0 meter`, `< 1 mm` dimensional error) for scale-locked WebAR placement on Android and iOS.

It runs **100% free and locally on CPU** (built and verified for Python 3.12 + Node 22 + `7.2 GiB` CPU-only systems without requiring a discrete GPU or paid APIs).

---

## Key Capabilities

1. **Core Backend (`backend/` — FastAPI + Python 3.12):**
   - **Memory-Safe Segmentation (`app/pipeline/segment.py`):** EXIF normalization, `1024 px` memory cap, CIE Lab studio background removal + OpenCV `GrabCut` refinement (plus optional `rembg` `u2netp` support), tight crop, and centered RGBA square padding.
   - **Pluggable Photo-to-3D Reconstruction (`app/pipeline/reconstruct.py`):**
     - *Multi-view (`2–6` photos):* Voxel visual-hull silhouette carving (`numpy`) + `scikit-image` Marching Cubes + Taubin smoothing (`trimesh`) + normal-weighted multi-angle color projection.
     - *Single-photo fallback:* Distance-transform rounded depth extrusion + color projection.
     - Engine registry ready for optional `triposr_local` / `hf_free_space` adapters.
   - **True-Scale Metric Normalization (`app/pipeline/scale.py`):** Converts `cm` / `mm` / `in` / `m` to meters, grounds the lowest vertex to `Y = 0.0`, centers `X/Z = 0.0`, scales to exact target `W × H × D` (`exact_fit` or `uniform` modes), and embeds scale verification metadata into exported `.glb` files.
   - **Job & Catalog API (`app/main.py`, `app/catalog.py`):** Bundled 5-product ShopScale sample catalog (`backend/assets/products/`), asynchronous reconstruction jobs, and `.glb` serving with `model/gltf-binary` + CORS headers.

2. **Frontend (`frontend/` — React + Vite + Three.js + `@google/model-viewer`):**
   - **ShopScale Storefront (`/` & `/product/:id`):** Amazon-inspired catalog with search, category filter, multi-angle photo gallery, specifications & dimensions table, **"Generate 3D from Listing Photos"**, and **"View in Your Room (True-Scale AR)"**.
   - **Photo-to-3D Studio (`/studio`):** Drag-and-drop 1–6 photos with angle selectors (`front`, `side`, `back`, `top`, `three_quarter`), `W × H × D` inputs with `cm` / `in` / `mm` live conversion, progress polling, and an interactive **Three.js 3D Scale Inspector** with toggleable metric wireframe, `10 cm` floor grid, `175 cm` human silhouette, `200 cm` doorframe, and `75 cm` desk.
   - **True-Scale AR Placement Viewer (`/ar/:id`):** Uses `<model-viewer ar ar-scale="fixed" ar-modes="webxr scene-viewer quick-look">` to lock `1:1` physical scale, browser-side `Three.js USDZExporter` for iOS AR Quick Look `.usdz` generation, and an editable **QR Code handoff modal** for scanning from a phone.

---

## Project Structure

```text
AR_VR_Project/
├── backend/
│   ├── app/
│   │   ├── catalog.py              # Sample ShopScale catalog & image resolver
│   │   ├── config.py               # Runtime settings (TRUESCALE_* env prefix)
│   │   ├── generate_assets.py      # Multi-angle PNG generator for sample catalog
│   │   ├── main.py                 # FastAPI endpoints & CORS
│   │   └── pipeline/
│   │       ├── reconstruct.py      # local_cpu 3D reconstructor & engine registry
│   │       ├── runner.py           # Disk-backed job pipeline orchestrator
│   │       ├── scale.py            # Metric normalization (1 unit = 1 m) & GLB export
│   │       └── segment.py          # CPU-fast RGBA segmentation & square crop
│   ├── assets/products/            # Bundled multi-angle PNGs for 5 sample products
│   ├── requirements.txt
│   └── tests/                      # Pytest unit + end-to-end API pipeline tests
├── frontend/
│   ├── src/
│   │   ├── api/client.js           # Shared backend API client & unit formatters
│   │   ├── components/
│   │   │   ├── ModelScaleInspector.jsx
│   │   │   ├── Navbar.jsx
│   │   │   └── QrShareModal.jsx
│   │   ├── pages/
│   │   │   ├── ArViewerPage.jsx
│   │   │   ├── ProductDetailPage.jsx
│   │   │   ├── StorefrontPage.jsx
│   │   │   └── StudioPage.jsx
│   │   └── utils/usdzExport.js     # Client-side Three.js USDZExporter
│   ├── package.json
│   └── vite.config.js              # Proxies /api -> http://127.0.0.1:8000
├── PRD.md
└── TODO.md
```

---

## Running Locally (Two Terminals)

### 1. Start the Backend API (Terminal 1)
```bash
cd backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Verify health at `http://127.0.0.1:8000/api/health`.

*(If setting up a fresh Python environment: `python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt`.)*

### 2. Start the Frontend Web App (Terminal 2)
```bash
cd frontend
npm install   # first time only
npm run dev
```
Open `http://localhost:5173` in your browser:
- **`/`** — ShopScale Dummy Storefront Demo
- **`/studio`** — Photo-to-3D True-Scale Studio
- **`/ar/:id`** — Locked `1:1` WebAR Placement Viewer

---

## Testing AR on a Phone (Same Wi-Fi or HTTPS Tunnel)

- **Android (Chrome WebXR / Scene Viewer) & iOS (Safari AR Quick Look):** Camera AR requires **HTTPS** (or `localhost`).
- Expose port `5173` (which already proxies `/api` to port `8000`) using a free quick tunnel such as `cloudflared tunnel --url http://localhost:5173` (or `ngrok http 5173`).
- On `/ar/:id`, click **"Scan QR to Place from Phone"**, paste the HTTPS tunnel URL into the modal input, and scan the QR code with your phone camera.

---

## Running Automated Tests

### Backend (`pytest`)
```bash
backend/.venv/bin/python -m pytest -v backend/tests
```

### Frontend (`vitest` + production `vite build`)
```bash
cd frontend
npm test
npm run build
```
