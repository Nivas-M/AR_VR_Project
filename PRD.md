# Product Requirements Document (PRD): TrueScale AR — Photo-to-True-Scale 3D & Shopping AR

## 1. Vision & Problem Statement
Online shoppers only see flat 2D product photos and text dimensions (e.g., `85 cm × 75 cm × 70 cm`), making it hard to tell how an item will look—or whether it will physically fit—in their actual room. Meanwhile, most small/mid-size e-commerce sites do not have 3D models for their products.

**TrueScale AR** solves this by:
1. Taking standard **product photos** (1 to 6 angles) + **real-world dimensions** (`Width × Height × Depth`).
2. Reconstructing a **textured 3D model (`.glb`)** using **100% free, open-source software** that runs locally on a standard PC.
3. Normalizing the 3D model to **exact real-world metric scale (`1 unit = 1 meter`)** grounded at `Y = 0`.
4. Letting the user **place the object in their real room via WebAR** at locked `1:1` scale (plus a **Dummy Amazon-style Storefront** to demonstrate the full shopping experience).

---

## 2. Target Environment & Hard Constraints
- **Cost:** `$0` — 100% free and open-source libraries, models, and tools only (no paid APIs or subscriptions).
- **Target Local Hardware (Verified):**
  - **CPU:** AMD Ryzen 5 3550H (4 cores / 8 threads, x86_64)
  - **GPU:** Integrated Radeon Vega (no NVIDIA CUDA GPU detected)
  - **RAM:** `7.2 GiB` total (~`1.4 GiB` typical free headroom + `2.0 GiB` swap)
- **Implication for Architecture:**
  - Heavy neural 3D diffusion models (e.g., Hunyuan3D-2, InstantMesh) require 12–24 GB VRAM/RAM and cannot run reliably on `7.2 GiB` CPU-only systems.
  - Therefore, the **primary engine MUST be lightweight, memory-safe (<500 MB peak working RAM), and CPU-fast** (`2–10 seconds` per object), using multi-view silhouette carving / depth-assisted textured mesh generation + lightweight ONNX segmentation.
  - A **pluggable reconstructor interface** will also allow optional heavier open-source engines (e.g., local `TripoSR` if run on a GPU machine, or optional free community ZeroGPU Space mode) without changing the rest of the pipeline.
- **Operating Rules:** Follow [AGENTS.md](file:///home/neev/Projects/AR-VR_Project/AGENTS.md) (plan before changes, only approved commands, user runs all servers).

---

## 3. System Components (Two Sites + One Core Backend)

### A. Core Backend: Photo-to-TrueScale-3D Engine (`backend/`)
Built with **Python 3.12 + FastAPI**:
1. **Image Preprocessing & Background Removal (`pipeline/segment.py`):**
   - Accepts 1–6 product photos (optionally tagged by view angle: `front`, `side`, `back`, `top`, `three_quarter`).
   - Removes solid/studio or cluttered backgrounds cleanly using lightweight open-source segmentation (lightweight ONNX `u2netp`/`silueta` or fast OpenCV GrabCut/flood-fill fallback tuned for low RAM) and normalizes framing.
2. **Pluggable 3D Mesh Reconstruction (`pipeline/reconstruct.py`):**
   - **Default (`local_cpu`):**
     - *Multi-angle mode (2+ photos):* Voxel visual-hull space carving (`numpy` + `scikit-image` Marching Cubes) + mesh smoothing (`trimesh`) + multi-view photo color/texture projection onto vertices/UVs.
     - *Single-photo mode (1 photo):* Lightweight symmetric depth/silhouette extrusion + front/back texture projection so even a single listing photo produces a valid 3D model in seconds on CPU.
   - **Optional (`triposr_local` / `hf_free_space`):** Pluggable adapter behind the same interface for GPU machines or optional free public Hugging Face Space inference.
3. **True-Scale Metric Normalization (`pipeline/scale.py`):**
   - Inputs: `width_cm`, `height_cm`, `depth_cm` (with `cm` / `in` / `mm` conversion) and `scale_mode` (`exact_fit` vs `uniform_height` / `uniform_width`).
   - Centers the mesh at `X = 0, Z = 0` and aligns the lowest vertex to `Y = 0` (floor plane).
   - Scales vertices so **`1.0 glTF unit = 1.0 meter`** matching the real product dimensions within `< 1 mm` precision.
   - Embeds scale verification metadata (`bounding_box_m`, `target_dimensions_m`, `aspect_delta`) in the API response and `.glb` extras.
4. **Job Pipeline, Storage & Catalog API (`main.py`):**
   - `GET /api/health` — system/engine readiness check.
   - `GET /api/products` & `GET /api/products/{id}` — sample dummy-Amazon products with multi-angle local photos & real dimensions.
   - `POST /api/reconstruct` — accepts uploaded images (or product ID) + `width_cm`, `height_cm`, `depth_cm` + `engine` mode; returns a `job_id`.
   - `GET /api/jobs/{job_id}` — returns status (`queued`, `segmenting`, `reconstructing`, `scaling`, `done`, `failed`), timing, and resulting `.glb` URL + measured dimensions.
   - `GET /api/models/{model_id}.glb` — serves the scaled `.glb` asset with proper `model/gltf-binary` MIME type and CORS headers for WebAR.

### B. Frontend Site 1: Dummy Amazon-Style Storefront (`/` and `/product/:id`)
A realistic mock e-commerce storefront (**"ShopScale"**) to demonstrate the shopping use case:
- Product catalog page with realistic furniture & home decor items (Armchair, Coffee Table, Floor Lamp, Bookshelf, Bluetooth Speaker).
- Amazon-style **Product Detail Page**:
  - Multi-angle photo gallery switcher.
  - Price, rating, description, and **"Product Dimensions & Technical Details"** table (`Width × Height × Depth` in `cm` & `inches`).
  - **"View in Your Room (True-Scale AR)"** CTA button: either opens the product's true-scale AR viewer directly OR sends its listing photos + parsed dimensions through the local backend pipeline live to prove it works end-to-end.

### C. Frontend Site 2: Actual Photo-to-3D & AR Studio (`/studio` and `/ar/:id`)
The real standalone tool that works for *any* product or object:
- **Photo-to-3D Studio (`/studio`):**
  - Upload 1–6 product photos (drag & drop) + assign view angle (`Front`, `Side`, `Back`, `Top`).
  - Enter real dimensions (`W × H × D`) with `cm` / `in` unit toggle (plus quick presets).
  - Live job progress tracker (`Segmenting → Reconstructing 3D → Scaling to Real Size`).
  - **Interactive 3D Scale Inspector (Three.js):** Orbit the generated `.glb`, toggle a **metric wireframe bounding box + live cm/inch dimension labels**, and toggle a **Virtual Living Room Scale Reference** (doorframe `200 cm`, coffee table, human silhouette `175 cm`) for desktop verification.
- **True-Scale AR Placement Page (`/ar/:id`):**
  - Powered by open-source **`@google/model-viewer`** with **`ar-scale="fixed"`** (prevents user pinch-resizing so size stays strictly 1:1 true-to-life).
  - Supports **Android** (WebXR / Google Scene Viewer) and **iOS** (browser-side `Three.js USDZExporter` → Apple AR Quick Look, zero backend Apple tools needed).
  - Includes a **QR Code Generator** (`qrcode.react` / `qrcode`) so you can run on your PC and scan with your phone on the same Wi-Fi/tunnel to place the object on your living room floor.

---

## 4. Development & Delivery Workflow
Strict feature-by-feature loop:
1. **Backend Core First** (Features 1 → 5)
2. **Frontend Second** (Features 6 → 9)
3. **One feature per iteration:** `Implement → Write & Run Automated Tests → Verify → Git Commit & Push → Next Feature`.

---

## 5. Success Criteria
- Generates a valid, textured `.glb` from local product photos on the `7.2 GiB` CPU-only PC without memory crashes.
- Automated unit tests verify that output `.glb` bounding box matches input `W × H × D` in meters (`Y_min == 0.0`, tolerance `< 0.001 m`).
- Dummy Amazon storefront demonstrates product dimensions + photo gallery → true-scale AR handoff seamlessly.
- Standalone `/studio` works for arbitrary user-uploaded photos + dimensions and produces a `1:1` scale-locked AR experience.
