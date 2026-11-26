"""FastAPI entrypoint for the TrueScale AR local backend."""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.catalog import get_product, get_product_image_path, list_products
from app.config import settings
from app.pipeline.reconstruct import get_engine, list_engines
from app.pipeline.runner import (
    read_job_state,
    read_model_metadata,
    run_reconstruction_job,
    write_job_state,
)
from app.pipeline.scale import ScaleMode, dimensions_to_meters

ALLOWED_SCALE_MODES = {
    "exact_fit",
    "uniform",
    "uniform_height",
    "uniform_width",
    "uniform_depth",
}


def ensure_storage_dirs() -> None:
    """Create local runtime storage subdirectories if missing."""
    for subdir in ("uploads", "models", "jobs"):
        (settings.storage_dir / subdir).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Prepare local storage directories on startup."""
    ensure_storage_dirs()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> dict[str, object]:
    """Return service readiness, active engine, and storage directory state."""
    ensure_storage_dirs()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "default_engine": settings.default_engine,
        "engines": list_engines(),
        "storage_ready": settings.storage_dir.exists(),
    }


@app.get("/api/products")
def api_list_products() -> dict[str, object]:
    """Return all bundled ShopScale sample products."""
    items = list_products()
    return {"products": items, "count": len(items)}


@app.get("/api/products/{product_id}")
def api_get_product(product_id: str) -> dict[str, object]:
    """Return details and real dimensions for one bundled product."""
    product = get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found")
    return product.to_dict()


@app.get("/api/products/{product_id}/images/{filename}")
def api_get_product_image(product_id: str, filename: str) -> FileResponse:
    """Serve a bundled multi-angle product image."""
    path = get_product_image_path(product_id, filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Product image not found")
    return FileResponse(path, media_type="image/png")


def _parse_angles(angles_raw: str | None, count: int) -> list[str]:
    """Parse optional JSON array or comma-separated angle tags."""
    if not angles_raw or not angles_raw.strip():
        return ["front" if i == 0 else "auto" for i in range(count)]

    stripped = angles_raw.strip()
    if stripped.startswith("["):
        parsed = json.loads(stripped)
        if isinstance(parsed, list):
            values = [str(item) for item in parsed]
        else:
            raise ValueError("angles JSON must be a list of strings")
    else:
        values = [part.strip() for part in stripped.split(",") if part.strip()]

    while len(values) < count:
        values.append("auto")
    return values[:count]


@app.post("/api/reconstruct")
async def api_reconstruct(
    background_tasks: BackgroundTasks,
    files: Annotated[list[UploadFile] | None, File()] = None,
    angles: Annotated[str | None, Form()] = None,
    product_id: Annotated[str | None, Form()] = None,
    width: Annotated[float | None, Form()] = None,
    height: Annotated[float | None, Form()] = None,
    depth: Annotated[float | None, Form()] = None,
    unit: Annotated[str, Form()] = "cm",
    scale_mode: Annotated[str, Form()] = "exact_fit",
    engine: Annotated[str, Form()] = "local_cpu",
    title: Annotated[str | None, Form()] = None,
) -> JSONResponse:
    """Queue a photo-to-true-scale-3D reconstruction job from uploads or a catalog product."""
    ensure_storage_dirs()

    if scale_mode not in ALLOWED_SCALE_MODES:
        raise HTTPException(status_code=400, detail=f"Unsupported scale_mode: {scale_mode}")

    try:
        selected_engine = get_engine(engine)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not selected_engine.is_available():
        raise HTTPException(
            status_code=400,
            detail=f"Engine '{engine}' is not available on this host; use 'local_cpu'.",
        )

    uploaded_files = [f for f in (files or []) if f.filename]
    if len(uploaded_files) > 6:
        raise HTTPException(status_code=400, detail="Maximum 6 photos are supported per job")

    job_id = uuid.uuid4().hex[:12]
    model_id = uuid.uuid4().hex[:12]
    image_inputs: list[tuple[Path, str]] = []
    resolved_title = (title or "").strip()

    if uploaded_files:
        if width is None or height is None or depth is None:
            raise HTTPException(
                status_code=400,
                detail="width, height, and depth are required when uploading photos",
            )
        try:
            parsed_angles = _parse_angles(angles, len(uploaded_files))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        upload_dir = settings.storage_dir / "uploads" / job_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        for idx, upload in enumerate(uploaded_files):
            suffix = Path(upload.filename or f"photo_{idx}.png").suffix.lower()
            if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
                suffix = ".png"
            dest = upload_dir / f"view_{idx}{suffix}"
            content = await upload.read()
            if not content:
                raise HTTPException(status_code=400, detail=f"Uploaded file '{upload.filename}' is empty")
            dest.write_bytes(content)
            image_inputs.append((dest, parsed_angles[idx]))

        if not resolved_title:
            resolved_title = f"Custom TrueScale Model ({width:g}×{height:g}×{depth:g} {unit})"
    elif product_id:
        product = get_product(product_id)
        if product is None:
            raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found")

        for img_meta in product.images:
            img_path = get_product_image_path(product.id, img_meta.filename)
            if img_path is not None:
                image_inputs.append((img_path, img_meta.angle))

        if not image_inputs:
            raise HTTPException(status_code=500, detail=f"No bundled assets found for '{product_id}'")

        width = width if width is not None else product.width_cm
        height = height if height is not None else product.height_cm
        depth = depth if depth is not None else product.depth_cm
        if not resolved_title:
            resolved_title = product.title
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide 1-6 image files or a valid product_id",
        )

    try:
        dimensions_to_meters(width, height, depth, unit=unit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    initial_state: dict[str, object] = {
        "job_id": job_id,
        "model_id": model_id,
        "title": resolved_title,
        "product_id": product_id,
        "status": "queued",
        "progress": 5,
        "stage_message": "Job queued for local processing",
        "engine": engine,
        "scale_mode": scale_mode,
        "unit": unit,
        "input_dimensions": {"width": width, "height": height, "depth": depth, "unit": unit},
        "model_url": None,
        "meta_url": None,
        "scale_report": None,
        "mesh_stats": None,
        "error": None,
    }
    write_job_state(settings.storage_dir / "jobs", job_id, initial_state)

    background_tasks.add_task(
        run_reconstruction_job,
        job_id=job_id,
        model_id=model_id,
        image_inputs=image_inputs,
        width=float(width),
        height=float(height),
        depth=float(depth),
        unit=unit,
        scale_mode=scale_mode,  # type: ignore[arg-type]
        engine=engine,
        title=resolved_title,
        storage_dir=settings.storage_dir,
        max_image_size_px=settings.max_image_size_px,
        voxel_resolution=settings.voxel_resolution,
        product_id=product_id,
    )

    return JSONResponse(status_code=202, content=initial_state)


@app.get("/api/jobs/{job_id}")
def api_get_job(job_id: str) -> dict[str, object]:
    """Return current pipeline status, scale verification, and output URLs for a job."""
    state = read_job_state(settings.storage_dir / "jobs", job_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return state


@app.get("/api/models/{model_id}.glb")
def api_get_model_glb(model_id: str) -> FileResponse:
    """Serve a scaled .glb 3D model with glTF-binary MIME type and WebAR CORS headers."""
    safe_id = Path(model_id).name
    glb_path = settings.storage_dir / "models" / f"{safe_id}.glb"
    if not glb_path.is_file():
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

    return FileResponse(
        glb_path,
        media_type="model/gltf-binary",
        filename=f"{safe_id}.glb",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=3600",
        },
    )


@app.get("/api/models/{model_id}/meta")
def api_get_model_meta(model_id: str) -> dict[str, object]:
    """Return scale report and mesh metadata for a generated .glb model."""
    safe_id = Path(model_id).name
    meta = read_model_metadata(settings.storage_dir / "models", safe_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Metadata for model '{model_id}' not found")
    return meta
