"""Unit tests for CPU-friendly photo-to-3D mesh reconstruction."""

import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh
from PIL import Image, ImageDraw

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.pipeline.reconstruct import (  # noqa: E402
    ViewInput,
    get_engine,
    list_engines,
    reconstruct_mesh,
)
from app.pipeline.scale import export_scaled_glb, normalize_mesh_to_metric_scale  # noqa: E402


def _make_rgba_silhouette(shape: str, fill: tuple[int, int, int, int], size: int = 256) -> Image.Image:
    """Create a centered RGBA silhouette image for reconstruction tests."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if shape == "box":
        draw.rectangle([48, 48, size - 48, size - 48], fill=fill)
    elif shape == "chair_front":
        draw.rectangle([58, 34, size - 58, 130], fill=fill)
        draw.rectangle([48, 124, size - 48, 162], fill=fill)
        draw.rectangle([56, 162, 78, size - 28], fill=fill)
        draw.rectangle([size - 78, 162, size - 56, size - 28], fill=fill)
    elif shape == "chair_side":
        draw.rectangle([142, 34, 174, 162], fill=fill)
        draw.rectangle([70, 124, 174, 162], fill=fill)
        draw.rectangle([72, 162, 94, size - 28], fill=fill)
        draw.rectangle([148, 162, 170, size - 28], fill=fill)
    elif shape == "cylinder":
        draw.ellipse([54, 44, size - 54, size - 44], fill=fill)
    return img


def test_single_view_reconstruction_produces_valid_glb(tmp_path: Path) -> None:
    """Single-photo fallback should produce a closed, colored mesh and valid .glb."""
    front = _make_rgba_silhouette("chair_front", fill=(52, 120, 152, 255))
    result = reconstruct_mesh([ViewInput(image=front, angle="front")], engine="local_cpu", resolution=48)

    assert result.engine_used == "local_cpu"
    assert result.mode_used == "single_view_extrusion"
    assert result.view_count == 1
    assert result.vertex_count > 100
    assert result.face_count > 100
    assert result.mesh.visual.vertex_colors is not None

    scaled, _ = normalize_mesh_to_metric_scale(result.mesh, width_m=0.75, height_m=0.82, depth_m=0.70)
    glb_path = tmp_path / "single_view.glb"
    export_scaled_glb(scaled, glb_path)

    loaded = trimesh.load(glb_path)
    assert isinstance(loaded, trimesh.Scene)
    assert loaded.extents == pytest.approx([0.75, 0.82, 0.70], abs=0.001)


def test_multi_view_reconstruction_carves_3d_silhouette_and_colors(tmp_path: Path) -> None:
    """Multi-view silhouette carving should combine front/side/back/top views cleanly."""
    views = [
        ViewInput(image=_make_rgba_silhouette("chair_front", fill=(38, 112, 148, 255)), angle="front"),
        ViewInput(image=_make_rgba_silhouette("chair_side", fill=(165, 92, 48, 255)), angle="side"),
        ViewInput(image=_make_rgba_silhouette("chair_front", fill=(45, 95, 130, 255)), angle="back"),
        ViewInput(image=_make_rgba_silhouette("box", fill=(90, 120, 110, 255)), angle="top"),
    ]

    result = reconstruct_mesh(views, engine="local_cpu", resolution=52)
    assert result.mode_used == "multi_view_visual_hull"
    assert result.view_count == 4
    assert result.vertex_count > 200
    assert result.face_count > 200

    # Verify vertex colors vary across views rather than being blank black/white.
    colors = np.asarray(result.mesh.visual.vertex_colors)[:, :3]
    assert colors.std() > 5.0

    scaled, _ = normalize_mesh_to_metric_scale(result.mesh, width_m=0.80, height_m=0.88, depth_m=0.76)
    glb_path = tmp_path / "multi_view.glb"
    export_scaled_glb(scaled, glb_path)

    loaded = trimesh.load(glb_path)
    assert isinstance(loaded, trimesh.Scene)
    assert loaded.extents == pytest.approx([0.80, 0.88, 0.76], abs=0.001)


def test_engine_registry_lists_local_and_optional_adapters() -> None:
    """Registry should expose local_cpu as available and optional GPU/cloud stubs."""
    engines = {item["name"]: item["available"] for item in list_engines()}
    assert engines["local_cpu"] is True
    assert "triposr_local" in engines
    assert "hf_free_space" in engines

    with pytest.raises(ValueError):
        get_engine("nonexistent_engine")
    with pytest.raises(RuntimeError):
        reconstruct_mesh([ViewInput(image=_make_rgba_silhouette("box", (200, 50, 50, 255)))], engine="triposr_local")
