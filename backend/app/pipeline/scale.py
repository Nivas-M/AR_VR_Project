"""True-scale metric mesh normalization for glTF/GLB assets (1 unit = 1 meter)."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import trimesh

ScaleMode = Literal[
    "exact_fit",
    "uniform",
    "uniform_height",
    "uniform_width",
    "uniform_depth",
]

UNIT_TO_METERS: dict[str, float] = {
    "m": 1.0,
    "meter": 1.0,
    "meters": 1.0,
    "cm": 0.01,
    "mm": 0.001,
    "in": 0.0254,
    "inch": 0.0254,
    "inches": 0.0254,
}


@dataclass(slots=True)
class ScaleReport:
    """Measured dimensions and scale verification metadata in meters."""

    scale_mode: str
    unit_input: str
    target_dimensions_m: dict[str, float]
    bounding_box_m: dict[str, float]
    scale_factors: dict[str, float]
    aspect_delta: dict[str, float]
    max_dimension_error_m: float

    def to_dict(self) -> dict[str, object]:
        """Serialize report into JSON-friendly dictionary."""
        return asdict(self)


def to_meters(value: float, unit: str = "cm") -> float:
    """Convert a positive finite measurement from cm/mm/in/m into meters."""
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"Dimension must be a positive finite number, got {value!r}")

    normalized_unit = unit.strip().lower()
    if normalized_unit not in UNIT_TO_METERS:
        supported = ", ".join(sorted(UNIT_TO_METERS))
        raise ValueError(f"Unsupported unit {unit!r}. Expected one of: {supported}")

    return float(value) * UNIT_TO_METERS[normalized_unit]


def dimensions_to_meters(
    width: float,
    height: float,
    depth: float,
    unit: str = "cm",
) -> tuple[float, float, float]:
    """Convert (width, height, depth) dimensions into (width_m, height_m, depth_m)."""
    return (
        to_meters(width, unit),
        to_meters(height, unit),
        to_meters(depth, unit),
    )


def _compute_scale_factors(
    extents: np.ndarray,
    target_m: tuple[float, float, float],
    scale_mode: ScaleMode,
) -> tuple[float, float, float]:
    """Calculate per-axis scale factors for the requested scaling mode."""
    ext_x, ext_y, ext_z = float(extents[0]), float(extents[1]), float(extents[2])
    target_x, target_y, target_z = target_m

    if scale_mode == "exact_fit":
        return (target_x / ext_x, target_y / ext_y, target_z / ext_z)
    if scale_mode == "uniform":
        factor = min(target_x / ext_x, target_y / ext_y, target_z / ext_z)
        return (factor, factor, factor)
    if scale_mode == "uniform_height":
        factor = target_y / ext_y
        return (factor, factor, factor)
    if scale_mode == "uniform_width":
        factor = target_x / ext_x
        return (factor, factor, factor)
    if scale_mode == "uniform_depth":
        factor = target_z / ext_z
        return (factor, factor, factor)

    raise ValueError(f"Unsupported scale_mode {scale_mode!r}")


def _extract_single_mesh(mesh_or_scene: trimesh.Trimesh | trimesh.Scene) -> trimesh.Trimesh:
    """Return a clean copy of a Trimesh, flattening Scene transforms if needed."""
    if isinstance(mesh_or_scene, trimesh.Trimesh):
        mesh = mesh_or_scene.copy()
    elif isinstance(mesh_or_scene, trimesh.Scene):
        if len(mesh_or_scene.geometry) == 0:
            raise ValueError("Cannot scale an empty trimesh.Scene")
        dumped = mesh_or_scene.dump(concatenate=True)
        if not isinstance(dumped, trimesh.Trimesh):
            raise ValueError("Scene did not contain valid triangle mesh geometry")
        mesh = dumped
    else:
        raise TypeError(f"Expected trimesh.Trimesh or trimesh.Scene, got {type(mesh_or_scene)!r}")

    if len(mesh.vertices) == 0:
        raise ValueError("Cannot scale a mesh with zero vertices")

    return mesh


def _transform_mesh_vertices(
    mesh: trimesh.Trimesh,
    scale_xyz: tuple[float, float, float],
) -> trimesh.Trimesh:
    """Scale vertices, ground lowest vertex to Y=0, and center X/Z at 0."""
    verts = np.asarray(mesh.vertices, dtype=np.float64).copy()
    scale_vec = np.asarray(scale_xyz, dtype=np.float64)
    verts *= scale_vec

    bmin = verts.min(axis=0)
    bmax = verts.max(axis=0)
    center_x = 0.5 * (bmin[0] + bmax[0])
    center_z = 0.5 * (bmin[2] + bmax[2])
    min_y = bmin[1]

    verts -= np.array([center_x, min_y, center_z], dtype=np.float64)
    # Clamp tiny floating-point subtraction drift on the floor plane to exact 0.0.
    verts[:, 1] -= verts[:, 1].min()
    mesh.vertices = verts

    if hasattr(mesh, "vertex_normals") and len(mesh.faces) > 0:
        mesh._cache.clear()

    return mesh


def normalize_mesh_to_metric_scale(
    mesh_or_scene: trimesh.Trimesh | trimesh.Scene,
    width_m: float,
    height_m: float,
    depth_m: float,
    scale_mode: ScaleMode = "exact_fit",
    unit_input: str = "m",
) -> tuple[trimesh.Trimesh, ScaleReport]:
    """Scale a mesh so 1.0 unit == 1.0 meter, grounded at Y=0 and centered on X/Z."""
    target_w = to_meters(width_m, "m")
    target_h = to_meters(height_m, "m")
    target_d = to_meters(depth_m, "m")

    mesh = _extract_single_mesh(mesh_or_scene)
    verts = np.asarray(mesh.vertices, dtype=np.float64)
    extents = verts.max(axis=0) - verts.min(axis=0)
    if np.any(extents <= 1e-9):
        raise ValueError(f"Mesh has degenerate zero-extent axis: {extents.tolist()}")

    scale_xyz = _compute_scale_factors(extents, (target_w, target_h, target_d), scale_mode)
    scaled_mesh = _transform_mesh_vertices(mesh, scale_xyz)

    scaled_verts = np.asarray(scaled_mesh.vertices, dtype=np.float64)
    bmin = scaled_verts.min(axis=0)
    bmax = scaled_verts.max(axis=0)
    measured = bmax - bmin

    mean_scale = float(np.mean(scale_xyz))
    err_w = abs(float(measured[0]) - target_w)
    err_h = abs(float(measured[1]) - target_h)
    err_d = abs(float(measured[2]) - target_d)

    aspect_delta = {
        "width_scale_deviation": round(float(scale_xyz[0] / mean_scale - 1.0), 6),
        "height_scale_deviation": round(float(scale_xyz[1] / mean_scale - 1.0), 6),
        "depth_scale_deviation": round(float(scale_xyz[2] / mean_scale - 1.0), 6),
        "max_scale_ratio_spread": round(float(max(scale_xyz) / min(scale_xyz) - 1.0), 6),
        "width_error_m": round(err_w, 6),
        "height_error_m": round(err_h, 6),
        "depth_error_m": round(err_d, 6),
    }

    report = ScaleReport(
        scale_mode=scale_mode,
        unit_input=unit_input,
        target_dimensions_m={
            "width": round(target_w, 6),
            "height": round(target_h, 6),
            "depth": round(target_d, 6),
        },
        bounding_box_m={
            "width": round(float(measured[0]), 6),
            "height": round(float(measured[1]), 6),
            "depth": round(float(measured[2]), 6),
            "min_x": round(float(bmin[0]), 6),
            "max_x": round(float(bmax[0]), 6),
            "min_y": round(float(bmin[1]), 6),
            "max_y": round(float(bmax[1]), 6),
            "min_z": round(float(bmin[2]), 6),
            "max_z": round(float(bmax[2]), 6),
        },
        scale_factors={
            "x": round(float(scale_xyz[0]), 6),
            "y": round(float(scale_xyz[1]), 6),
            "z": round(float(scale_xyz[2]), 6),
        },
        aspect_delta=aspect_delta,
        max_dimension_error_m=round(max(err_w, err_h, err_d), 6),
    )

    scaled_mesh.metadata["truescale"] = report.to_dict()
    return scaled_mesh, report


def export_scaled_glb(
    mesh: trimesh.Trimesh,
    output_path: str | Path | None = None,
    report: ScaleReport | None = None,
) -> bytes:
    """Export a scaled mesh as binary glTF (.glb) with embedded scale metadata."""
    scene = trimesh.Scene()
    scene.add_geometry(mesh, node_name="truescale_product", geom_name="truescale_product")
    if report is not None:
        scene.metadata["truescale"] = report.to_dict()
    elif "truescale" in mesh.metadata:
        scene.metadata["truescale"] = mesh.metadata["truescale"]

    glb_bytes = trimesh.exchange.gltf.export_glb(scene, include_normals=True)
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(glb_bytes)
    return glb_bytes
