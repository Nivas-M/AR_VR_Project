# Implementation TODO List (Implement → Test → Commit & Push)

> **Workflow Rule:** Work strictly **one feature at a time**, completing **Backend Core** before **Frontend**.
> Each feature follows: **Implement → Test → Verify → Commit & Push**.

---

## Phase 0: Repository Setup & Planning (Current)
- [x] Inspect workspace & local PC hardware (`Python 3.12.3`, `Node v22.23.5`, Ryzen 5 3550H CPU, `7.2 GiB` RAM, no NVIDIA GPU)
- [x] Initialize git repository (`main`) and configure `origin` (`https://github.com/Nivas-M/AR_VR_Project.git`)
- [x] Write `PRD.md`, `TODO.md`, and `.gitignore`
- [x] Commit & push initial project docs (`AGENTS.md`, `PRD.md`, `TODO.md`, `.gitignore`)

---

## Part 1: Backend Core (`backend/`)

### Feature 1: Backend Scaffold, Config & Health Check API
- [x] Create `backend/` directory structure, `requirements.txt`, `app/config.py`, `app/main.py` (`GET /api/health`)
- [x] Create virtual environment (`backend/.venv`) and install base dependencies (`fastapi`, `uvicorn`, `pydantic`, `httpx`, `pytest`)
- [x] Test: Unit/API test for `GET /api/health` using FastAPI `TestClient`
- [x] Commit & Push: `feat(backend): scaffold FastAPI app and health check endpoint`

### Feature 2: True-Scale Metric Mesh Normalization (`scale.py`)
- [x] Implement `backend/app/pipeline/scale.py` using `trimesh` + `numpy`:
  - Unit conversion (`cm`, `mm`, `in` → `meters`)
  - Ground mesh bottom to `Y = 0`, center `X = 0, Z = 0`
  - Rescale bounding box to match target `width_m × height_m × depth_m` (`exact_fit` and `uniform` modes)
  - Return measured bounding box & aspect-ratio delta report
- [x] Test: `backend/tests/test_scale.py` verifying box/cylinder/asymmetric meshes scale to exact meters (`< 1 mm` error) and `min_y == 0.0`
- [x] Commit & Push: `feat(backend): add true-scale metric mesh normalization module`

### Feature 3: Photo Segmentation & Background Removal (`segment.py`)
- [x] Implement `backend/app/pipeline/segment.py`:
  - Resize/normalize input images safely (memory cap for `7.2 GiB` RAM)
  - Foreground mask extraction (lightweight CPU-friendly segmentation: studio background removal + OpenCV/PIL GrabCut/edge-aware fallback, plus optional `rembg` `u2netp` support)
  - Tight crop & square pad centered foreground RGBA output
- [x] Test: `backend/tests/test_segment.py` with synthetic product images (white bg + colored bg) verifying clean alpha mask & bounding crop
- [x] Commit & Push: `feat(backend): add memory-safe image segmentation and preprocessing`

### Feature 4: Local CPU Photo-to-3D Reconstruction Engine (`reconstruct.py`)
- [x] Implement pluggable `backend/app/pipeline/reconstruct.py`:
  - `local_cpu` engine:
    - Multi-view silhouette carving (`numpy` voxel grid + `scikit-image` Marching Cubes) + Laplacian smoothing (`trimesh`) + multi-angle photo color projection → textured `.glb`
    - Single-photo fallback: symmetric depth/profile extrusion + front/back photo color mapping → textured `.glb`
  - Engine registry interface ready for optional `triposr_local` / `hf_free_space`
- [x] Test: `backend/tests/test_reconstruct.py` generating `.glb` files from 1-view and multi-view synthetic RGBA silhouettes, checking valid glTF export & non-empty geometry
- [x] Commit & Push: `feat(backend): add CPU-friendly photo-to-3D mesh reconstruction pipeline`

### Feature 5: End-to-End Pipeline API & Dummy Store Sample Catalog (`main.py` + `catalog.py`)
- [x] Create bundled sample product assets (`backend/assets/products/`) with multi-angle PNGs and real dimensions (`W × H × D`)
- [x] Implement `POST /api/reconstruct`, `GET /api/jobs/{job_id}`, `GET /api/models/{model_id}.glb`, `GET /api/products`, `GET /api/products/{id}`
- [x] Wire full pipeline: `upload/product photos → segment → reconstruct → metric scale → save .glb`
- [x] Test: `backend/tests/test_api_pipeline.py` end-to-end API test verifying a submitted photo set produces a downloadable `.glb` whose bounding box matches requested real-world meters
- [x] Commit & Push: `feat(backend): add reconstruction job API, GLB serving, and sample catalog`

---

## Part 2: Frontend (`frontend/`)

### Feature 6: Frontend Scaffold, Routing & Shared API Client
- [ ] Scaffold Vite + React app in `frontend/` (`react-router-dom`, `three`, `@google/model-viewer`, `qrcode.react`, `lucide-react`)
- [ ] Create shared API client (`frontend/src/api/client.js`), navigation bar switching cleanly between **Dummy Storefront** and **Photo-to-3D Studio**, and `vite.config.js` `/api` proxy
- [ ] Test: `npm run build` + unit/smoke test verifying routes & API client helpers
- [ ] Commit & Push: `feat(frontend): scaffold React app, routing, and backend API client`

### Feature 7: Actual App — Photo-to-3D True-Scale Studio (`/studio`)
- [ ] Build `StudioPage.jsx` with multi-photo uploader (1–6 photos + angle selector `front/side/back/top`), dimension inputs (`W × H × D` with `cm`/`in` toggle), and live pipeline progress polling
- [ ] Build Three.js `ModelScaleInspector.jsx` showing the reconstructed `.glb`, toggleable metric bounding-box wireframe, live dimension labels, and Virtual Room Reference props (`175 cm` person / `200 cm` doorframe / desk)
- [ ] Test: Component/build tests + live verification against backend API output
- [ ] Commit & Push: `feat(frontend): add Photo-to-3D True-Scale Studio and 3D dimension inspector`

### Feature 8: True-Scale AR Placement Viewer (`/ar/:id`)
- [ ] Build `ArViewerPage.jsx` using `<model-viewer>` with `ar`, `ar-scale="fixed"`, `ar-modes="webxr scene-viewer quick-look"`
- [ ] Add browser-side `Three.js USDZExporter` for iOS AR Quick Look support + QR code modal for scanning from a phone on local network/tunnel
- [ ] Test: `npm run build` + verify `USDZExporter` & `<model-viewer>` props (locked `1:1` scale)
- [ ] Commit & Push: `feat(frontend): add true-scale locked WebAR viewer, iOS USDZ export, and QR handoff`

### Feature 9: Dummy Amazon-Style E-Commerce Demo (`/` & `/product/:id`)
- [ ] Build `StorefrontPage.jsx` and `ProductDetailPage.jsx` ("ShopScale" Amazon-like UI) with search/filter, multi-angle gallery, and "Product Specifications & Dimensions" table
- [ ] Wire **"View in Your Room (True-Scale AR)"** and **"Generate 3D from Listing Photos"** buttons directly into the backend pipeline & `/ar/:id` viewer
- [ ] Test: `npm run build` + end-to-end flow check (Storefront → Generate 3D → True-Scale AR Viewer) + write final `README.md` with server run instructions for the user
- [ ] Commit & Push: `feat(frontend): add ShopScale dummy e-commerce storefront demo and README`
