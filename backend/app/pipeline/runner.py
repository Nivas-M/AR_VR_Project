"""End-to-end reconstruction job runner and disk-backed state persistence."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from app.pipeline.reconstruct import ViewInput, reconstruct_mesh
from app.pipeline.scale import (
    ScaleMode,
    dimensions_to_meters,
    export_scaled_glb,
    normalize_mesh_to_metric_scale,
)
from app.pipeline.segment import segment_image


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_job_state(jobs_dir: Path, job_id: str, payload: dict[str, object]) -> None:
    """Atomically write job status JSON to disk."""
    jobs_dir.mkdir(parents=True, exist_ok=True)
    target = jobs_dir / f"{job_id}.json"
    tmp = jobs_dir / f"{job_id}.json.tmp"
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(target)


def read_job_state(jobs_dir: Path, job_id: str) -> dict[str, object] | None:
    """Load persisted job status JSON if present."""
    path = jobs_dir / f"{job_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_model_metadata(models_dir: Path, model_id: str) -> dict[str, object] | None:
    """Load persisted model metadata JSON if present."""
    path = models_dir / f"{model_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def run_reconstruction_job(
    *,
    job_id: str,
    model_id: str,
    image_inputs: Sequence[tuple[Path, str]],
    width: float,
    height: float,
    depth: float,
    unit: str,
    scale_mode: ScaleMode,
    engine: str,
    title: str,
    storage_dir: Path,
    max_image_size_px: int = 1024,
    voxel_resolution: int = 68,
    product_id: str | None = None,
) -> None:
    """Execute segment -> reconstruct -> metric scale -> export .glb for a job."""
    jobs_dir = storage_dir / "jobs"
    models_dir = storage_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    existing = read_job_state(jobs_dir, job_id) or {}
    created_at = str(existing.get("created_at") or _utc_now_iso())

    def update(
        status: str,
        progress: int,
        stage_message: str,
        **extra: object,
    ) -> None:
        state: dict[str, object] = {
            "job_id": job_id,
            "model_id": model_id,
            "title": title,
            "product_id": product_id,
            "status": status,
            "progress": progress,
            "stage_message": stage_message,
            "engine": engine,
            "scale_mode": scale_mode,
            "unit": unit,
            "input_dimensions": {"width": width, "height": height, "depth": depth, "unit": unit},
            "created_at": created_at,
            "updated_at": _utc_now_iso(),
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "model_url": None,
            "meta_url": None,
            "scale_report": None,
            "mesh_stats": None,
            "error": None,
        }
        state.update(extra)
        write_job_state(jobs_dir, job_id, state)

    try:
        update("segmenting", 20, f"Removing background from {len(image_inputs)} photo(s)...")
        segmented_views: list[ViewInput] = []
        segmentation_methods: list[str] = []
        for path, angle in image_inputs:
            seg = segment_image(path, max_image_size_px=max_image_size_px, output_size=384)
            segmented_views.append(ViewInput(image=seg.rgba_image, angle=angle))
            segmentation_methods.append(seg.method_used)

        update("reconstructing", 55, f"Reconstructing 3D geometry ({engine})...")
        recon = reconstruct_mesh(segmented_views, engine=engine, resolution=voxel_resolution)

        update("scaling", 85, "Normalizing 3D mesh to exact metric scale (1 unit = 1 meter)...")
        width_m, height_m, depth_m = dimensions_to_meters(width, height, depth, unit=unit)
        scaled_mesh, scale_report = normalize_mesh_to_metric_scale(
            recon.mesh,
            width_m=width_m,
            height_m=height_m,
            depth_m=depth_m,
            scale_mode=scale_mode,
            unit_input=unit,
        )

        glb_path = models_dir / f"{model_id}.glb"
        export_scaled_glb(scaled_mesh, glb_path, report=scale_report)

        report_dict = scale_report.to_dict()
        mesh_stats = {
            "vertex_count": recon.vertex_count,
            "face_count": recon.face_count,
            "mode_used": recon.mode_used,
            "engine_used": recon.engine_used,
            "view_count": recon.view_count,
            "voxel_resolution": recon.voxel_resolution,
            "segmentation_methods": segmentation_methods,
            "glb_size_bytes": glb_path.stat().st_size,
        }
        model_url = f"/api/models/{model_id}.glb"
        meta_url = f"/api/models/{model_id}/meta"

        model_meta = {
            "model_id": model_id,
            "job_id": job_id,
            "title": title,
            "product_id": product_id,
            "model_url": model_url,
            "created_at": created_at,
            "scale_report": report_dict,
            "mesh_stats": mesh_stats,
        }
        (models_dir / f"{model_id}.json").write_text(
            json.dumps(model_meta, indent=2),
            encoding="utf-8",
        )

        update(
            "done",
            100,
            "True-scale 3D model ready",
            model_url=model_url,
            meta_url=meta_url,
            scale_report=report_dict,
            mesh_stats=mesh_stats,
        )
    except Exception as exc:  # noqa: BLE001
        update(
            "failed",
            100,
            "Pipeline failed",
            error=str(exc),
        )
