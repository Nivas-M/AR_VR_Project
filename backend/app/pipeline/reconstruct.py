"""Pluggable CPU-friendly photo-to-3D mesh reconstruction pipeline."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence

import cv2
import numpy as np
import trimesh
from PIL import Image
from skimage.measure import marching_cubes

SUPPORTED_ANGLES = (
    "front",
    "back",
    "left",
    "right",
    "side",
    "top",
    "three_quarter",
    "three_quarter_right",
    "three_quarter_left",
)


@dataclass(slots=True)
class ViewInput:
    """Segmented RGBA photo paired with its nominal camera angle."""

    image: Image.Image
    angle: str = "front"


@dataclass(slots=True)
class ReconstructionResult:
    """Output mesh and reconstruction telemetry."""

    mesh: trimesh.Trimesh
    engine_used: str
    mode_used: str
    view_count: int
    vertex_count: int
    face_count: int
    voxel_resolution: int


class BaseReconstructor(ABC):
    """Abstract interface for pluggable 3D reconstruction backends."""

    name: str

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if runtime dependencies for this engine are available."""

    @abstractmethod
    def reconstruct(
        self,
        views: Sequence[ViewInput],
        resolution: int = 68,
    ) -> ReconstructionResult:
        """Reconstruct a textured/vertex-colored 3D mesh from segmented RGBA views."""


def _normalize_angle(angle: str, index: int) -> str:
    """Canonicalize angle labels and assign defaults for unrecognized/auto tags."""
    cleaned = angle.strip().lower().replace("-", "_").replace(" ", "_")
    if cleaned in SUPPORTED_ANGLES:
        return "right" if cleaned == "side" else cleaned
    fallback_ring = ["front", "right", "back", "left", "three_quarter", "top"]
    return fallback_ring[index % len(fallback_ring)]


def _view_direction(angle: str) -> np.ndarray:
    """Unit vector pointing from origin toward the camera for each canonical angle."""
    inv_sqrt2 = 1.0 / math.sqrt(2.0)
    directions = {
        "front": np.array([0.0, 0.0, 1.0], dtype=np.float32),
        "back": np.array([0.0, 0.0, -1.0], dtype=np.float32),
        "right": np.array([1.0, 0.0, 0.0], dtype=np.float32),
        "left": np.array([-1.0, 0.0, 0.0], dtype=np.float32),
        "three_quarter": np.array([inv_sqrt2, 0.0, inv_sqrt2], dtype=np.float32),
        "three_quarter_right": np.array([inv_sqrt2, 0.0, inv_sqrt2], dtype=np.float32),
        "three_quarter_left": np.array([-inv_sqrt2, 0.0, inv_sqrt2], dtype=np.float32),
        "top": np.array([0.0, 1.0, 0.0], dtype=np.float32),
    }
    return directions[angle]


def _project_points_to_uv(
    points: np.ndarray,
    angle: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Project normalized 3D coordinates in [-1, 1]^3 to image UV in [0, 1]^2."""
    x = points[..., 0]
    y = points[..., 1]
    z = points[..., 2]
    inv_sqrt2 = 1.0 / math.sqrt(2.0)

    if angle == "front":
        cam_x, cam_y = x, y
    elif angle == "back":
        cam_x, cam_y = -x, y
    elif angle == "right":
        cam_x, cam_y = -z, y
    elif angle == "left":
        cam_x, cam_y = z, y
    elif angle in ("three_quarter", "three_quarter_right"):
        cam_x, cam_y = (x - z) * inv_sqrt2, y
    elif angle == "three_quarter_left":
        cam_x, cam_y = (x + z) * inv_sqrt2, y
    elif angle == "top":
        cam_x, cam_y = x, -z
    else:
        cam_x, cam_y = x, y

    u = 0.5 * (cam_x + 1.0)
    v = 0.5 * (1.0 - cam_y)
    return u, v


def _prepare_view_arrays(
    view: ViewInput,
    target_size: int = 256,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extract foreground-bleed-cleaned RGB and smooth alpha mask from an RGBA view."""
    rgba = view.image.convert("RGBA").resize(
        (target_size, target_size),
        Image.Resampling.BILINEAR,
    )
    arr = np.asarray(rgba)
    rgb = arr[:, :, :3].copy()
    alpha = arr[:, :, 3].astype(np.float32) / 255.0

    # Dilate foreground RGB outward into transparent pixels so edge samples stay clean.
    fg_mask = (arr[:, :, 3] > 24).astype(np.uint8)
    if np.any(fg_mask):
        dilated = rgb.copy()
        kernel = np.ones((5, 5), dtype=np.uint8)
        empty = fg_mask == 0
        for _ in range(4):
            step = cv2.dilate(dilated, kernel)
            dilated[empty] = step[empty]
        rgb = dilated

    # Smooth alpha lightly for anti-aliased visual hull carving.
    smooth_alpha = cv2.GaussianBlur(alpha, (5, 5), sigmaX=1.0)
    return rgb, alpha, smooth_alpha


def _sample_2d(field: np.ndarray, u: np.ndarray, v: np.ndarray, fill: float = 0.0) -> np.ndarray:
    """Bilinearly sample a 2D array at normalized (u, v) coordinates."""
    h, w = field.shape[:2]
    x = u * (w - 1)
    y = v * (h - 1)
    in_bounds = (x >= 0.0) & (x <= w - 1) & (y >= 0.0) & (y <= h - 1)

    x_clipped = np.clip(x, 0.0, w - 1.0001)
    y_clipped = np.clip(y, 0.0, h - 1.0001)
    x0 = np.floor(x_clipped).astype(np.int32)
    y0 = np.floor(y_clipped).astype(np.int32)
    x1 = np.minimum(x0 + 1, w - 1)
    y1 = np.minimum(y0 + 1, h - 1)

    wx = (x_clipped - x0).astype(np.float32)
    wy = (y_clipped - y0).astype(np.float32)

    if field.ndim == 2:
        out = (
            field[y0, x0] * (1.0 - wx) * (1.0 - wy)
            + field[y0, x1] * wx * (1.0 - wy)
            + field[y1, x0] * (1.0 - wx) * wy
            + field[y1, x1] * wx * wy
        )
        out[~in_bounds] = fill
        return out

    wx3 = wx[..., None]
    wy3 = wy[..., None]
    out = (
        field[y0, x0] * (1.0 - wx3) * (1.0 - wy3)
        + field[y0, x1] * wx3 * (1.0 - wy3)
        + field[y1, x0] * (1.0 - wx3) * wy3
        + field[y1, x1] * wx3 * wy3
    )
    return out


def _single_view_depth_volume(
    smooth_alpha: np.ndarray,
    grid_points: np.ndarray,
) -> np.ndarray:
    """Build a symmetric rounded 3D occupancy volume from one front silhouette."""
    binary = (smooth_alpha > 0.45).astype(np.uint8)
    dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5).astype(np.float32)
    max_dist = float(dist.max())
    if max_dist <= 1e-6:
        raise ValueError("Input image contains no foreground silhouette")

    # Depth envelope tapers smoothly to zero at silhouette boundary for watertightness.
    norm_dist = np.clip(dist / max_dist, 0.0, 1.0)
    half_thickness = 0.22 + 0.60 * np.sqrt(norm_dist)
    half_thickness[binary == 0] = 0.0
    half_thickness = cv2.GaussianBlur(half_thickness, (5, 5), sigmaX=1.0)

    u, v = _project_points_to_uv(grid_points, "front")
    sampled_alpha = _sample_2d(smooth_alpha, u, v, fill=0.0)
    sampled_thickness = _sample_2d(half_thickness, u, v, fill=0.0)

    abs_z = np.abs(grid_points[..., 2])
    z_profile = np.clip((sampled_thickness - abs_z) / 0.14 + 0.5, 0.0, 1.0)
    return np.minimum(sampled_alpha, z_profile)


def _carve_multi_view_volume(
    prepared_views: list[tuple[str, np.ndarray, np.ndarray, np.ndarray]],
    grid_points: np.ndarray,
) -> np.ndarray:
    """Intersect per-view silhouette occupancy fields in 3D voxel space."""
    occupancy = np.ones(grid_points.shape[:3], dtype=np.float32)
    angles_present = {angle for angle, _, _, _ in prepared_views}

    for angle, _, _, smooth_alpha in prepared_views:
        u, v = _project_points_to_uv(grid_points, angle)
        sampled = _sample_2d(smooth_alpha, u, v, fill=0.0)
        occupancy = np.minimum(occupancy, sampled)

    # If views only cover front/back (no side/3-quarter/top depth constraint),
    # bound Z smoothly using the front silhouette's distance envelope.
    has_depth_view = bool(
        angles_present & {"left", "right", "top", "three_quarter", "three_quarter_right", "three_quarter_left"}
    )
    if not has_depth_view:
        front_alpha = prepared_views[0][3]
        depth_vol = _single_view_depth_volume(front_alpha, grid_points)
        occupancy = np.minimum(occupancy, depth_vol)

    return occupancy


def _extract_and_smooth_mesh(volume: np.ndarray, grid_extent: float = 1.08) -> trimesh.Trimesh:
    """Run Marching Cubes on padded voxel occupancy and apply Taubin smoothing."""
    padded = np.pad(volume, pad_width=2, mode="constant", constant_values=0.0)
    if float(padded.max()) < 0.5:
        raise ValueError("Voxel carving produced an empty volume; check foreground silhouettes")

    verts, faces, _, _ = marching_cubes(padded, level=0.5)
    # Map padded voxel indices back to normalized world space [-grid_extent, +grid_extent].
    n = volume.shape[0]
    verts_norm = ((verts - 2.0) / float(n - 1)) * 2.0 * grid_extent - grid_extent

    mesh = trimesh.Trimesh(vertices=verts_norm, faces=faces, process=True)
    if len(mesh.faces) == 0 or len(mesh.vertices) == 0:
        raise ValueError("Marching Cubes produced an empty triangle mesh")

    # Keep the primary connected component if tiny floating voxel artifacts exist.
    components = mesh.split(only_watertight=False)
    if len(components) > 1:
        mesh = max(components, key=lambda c: len(c.faces))

    # Taubin smoothing removes voxel staircase artifacts without shrinking volume.
    trimesh.smoothing.filter_taubin(mesh, lamb=0.45, nu=-0.42, iterations=6)
    mesh.fix_normals()
    return mesh


def _project_vertex_colors(
    mesh: trimesh.Trimesh,
    prepared_views: list[tuple[str, np.ndarray, np.ndarray, np.ndarray]],
) -> trimesh.Trimesh:
    """Project multi-angle photo colors onto mesh vertices weighted by surface normals."""
    verts = np.asarray(mesh.vertices, dtype=np.float32)
    normals = np.asarray(mesh.vertex_normals, dtype=np.float32)

    # Normalize vertices into [-0.95, 0.95] bounding cube for crisp photo lookup.
    bmin = verts.min(axis=0)
    bmax = verts.max(axis=0)
    center = 0.5 * (bmin + bmax)
    half_span = max(float(np.max(bmax - bmin)) * 0.5, 1e-6)
    norm_verts = ((verts - center) / half_span) * 0.84

    accum_rgb = np.zeros((len(verts), 3), dtype=np.float32)
    accum_weight = np.zeros((len(verts), 1), dtype=np.float32)

    for angle, rgb, alpha, _ in prepared_views:
        cam_dir = _view_direction(angle)
        dots = np.clip(normals @ cam_dir, 0.0, 1.0)
        view_weight = (dots**2 + 0.03)[:, None]

        u, v = _project_points_to_uv(norm_verts, angle)
        sampled_rgb = _sample_2d(rgb.astype(np.float32), u, v, fill=128.0)
        sampled_alpha = _sample_2d(alpha, u, v, fill=0.0)[:, None]

        # Prefer views where vertex projects solidly inside the foreground silhouette.
        alpha_confidence = np.clip(sampled_alpha, 0.08, 1.0)
        weight = view_weight * alpha_confidence

        accum_rgb += sampled_rgb * weight
        accum_weight += weight

    final_rgb = np.clip(accum_rgb / np.maximum(accum_weight, 1e-6), 0.0, 255.0).astype(np.uint8)
    rgba = np.column_stack([final_rgb, np.full((len(verts), 1), 255, dtype=np.uint8)])
    mesh.visual = trimesh.visual.ColorVisuals(mesh=mesh, vertex_colors=rgba)
    return mesh


class LocalCpuReconstructor(BaseReconstructor):
    """Lightweight CPU-fast visual hull + single-view depth extrusion engine."""

    name = "local_cpu"

    def is_available(self) -> bool:
        return True

    def reconstruct(
        self,
        views: Sequence[ViewInput],
        resolution: int = 68,
    ) -> ReconstructionResult:
        if not views:
            raise ValueError("At least one segmented view is required for reconstruction")
        if not (24 <= resolution <= 128):
            raise ValueError(f"Voxel resolution must be between 24 and 128, got {resolution}")

        prepared: list[tuple[str, np.ndarray, np.ndarray, np.ndarray]] = []
        used_angles: list[str] = []
        for idx, view in enumerate(views):
            angle = _normalize_angle(view.angle, idx)
            # Disambiguate repeated default 'front' tags across multi-photo uploads.
            if idx > 0 and angle in used_angles and view.angle.strip().lower() in ("", "auto", "front"):
                angle = _normalize_angle("auto", idx)
            used_angles.append(angle)
            rgb, alpha, smooth_alpha = _prepare_view_arrays(view)
            prepared.append((angle, rgb, alpha, smooth_alpha))

        grid_extent = 1.08
        axis = np.linspace(-grid_extent, grid_extent, resolution, dtype=np.float32)
        gx, gy, gz = np.meshgrid(axis, axis, axis, indexing="ij")
        grid_points = np.stack([gx, gy, gz], axis=-1)

        if len(prepared) == 1:
            volume = _single_view_depth_volume(prepared[0][3], grid_points)
            mode_used = "single_view_extrusion"
        else:
            volume = _carve_multi_view_volume(prepared, grid_points)
            mode_used = "multi_view_visual_hull"

        mesh = _extract_and_smooth_mesh(volume, grid_extent=grid_extent)
        mesh = _project_vertex_colors(mesh, prepared)

        return ReconstructionResult(
            mesh=mesh,
            engine_used=self.name,
            mode_used=mode_used,
            view_count=len(prepared),
            vertex_count=len(mesh.vertices),
            face_count=len(mesh.faces),
            voxel_resolution=resolution,
        )


class OptionalExternalReconstructor(BaseReconstructor):
    """Adapter placeholder for optional GPU/cloud engines (TripoSR, HF ZeroGPU Space)."""

    def __init__(self, name: str, required_module: str, install_hint: str) -> None:
        self.name = name
        self._required_module = required_module
        self._install_hint = install_hint

    def is_available(self) -> bool:
        try:
            __import__(self._required_module)
            return True
        except ImportError:
            return False

    def reconstruct(
        self,
        views: Sequence[ViewInput],
        resolution: int = 68,
    ) -> ReconstructionResult:
        raise RuntimeError(
            f"Engine '{self.name}' is not active in local CPU mode ({self._install_hint}). "
            "Use 'local_cpu' for zero-cost local reconstruction."
        )


ENGINE_REGISTRY: dict[str, BaseReconstructor] = {}


def register_engine(engine: BaseReconstructor) -> None:
    """Register a reconstructor implementation by name."""
    ENGINE_REGISTRY[engine.name] = engine


def get_engine(name: str = "local_cpu") -> BaseReconstructor:
    """Look up a registered 3D reconstruction engine."""
    if name not in ENGINE_REGISTRY:
        available = ", ".join(sorted(ENGINE_REGISTRY))
        raise ValueError(f"Unknown reconstruction engine {name!r}. Registered: {available}")
    return ENGINE_REGISTRY[name]


def list_engines() -> list[dict[str, object]]:
    """Return engine availability metadata for health/UI inspection."""
    return [
        {"name": name, "available": engine.is_available()}
        for name, engine in ENGINE_REGISTRY.items()
    ]


def reconstruct_mesh(
    views: Sequence[ViewInput],
    engine: str = "local_cpu",
    resolution: int = 68,
) -> ReconstructionResult:
    """Reconstruct a 3D mesh using the requested registered engine."""
    reconstructor = get_engine(engine)
    return reconstructor.reconstruct(views=views, resolution=resolution)


register_engine(LocalCpuReconstructor())
register_engine(
    OptionalExternalReconstructor(
        name="triposr_local",
        required_module="tsr",
        install_hint="requires CUDA GPU + TripoSR weights",
    )
)
register_engine(
    OptionalExternalReconstructor(
        name="hf_free_space",
        required_module="gradio_client",
        install_hint="optional remote Hugging Face Space adapter",
    )
)
