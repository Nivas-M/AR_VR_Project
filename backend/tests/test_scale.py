"""Unit tests for true-scale metric mesh normalization."""

import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.pipeline.scale import (  # noqa: E402
    dimensions_to_meters,
    export_scaled_glb,
    normalize_mesh_to_metric_scale,
    to_meters,
)


def test_unit_conversions_and_validation() -> None:
    """Unit helpers should convert cm/mm/in/m accurately and reject bad inputs."""
    assert to_meters(85.0, "cm") == pytest.approx(0.85, abs=1e-9)
    assert to_meters(1200.0, "mm") == pytest.approx(1.2, abs=1e-9)
    assert to_meters(10.0, "in") == pytest.approx(0.254, abs=1e-9)
    assert dimensions_to_meters(80, 75, 70, "cm") == pytest.approx((0.80, 0.75, 0.70), abs=1e-9)

    with pytest.raises(ValueError):
        to_meters(-5.0, "cm")
    with pytest.raises(ValueError):
        to_meters(10.0, "ft")


def test_box_mesh_exact_fit_grounding_and_centering() -> None:
    """An off-center floating box should scale within < 1 mm and sit at Y=0."""
    box = trimesh.creation.box(extents=[2.0, 4.0, 1.5])
    box.apply_translation([5.0, -3.25, -4.0])

    scaled, report = normalize_mesh_to_metric_scale(
        box,
        width_m=0.85,
        height_m=0.78,
        depth_m=0.72,
        scale_mode="exact_fit",
        unit_input="cm",
    )

    bmin, bmax = scaled.bounds
    extents = bmax - bmin
    assert bmin[1] == pytest.approx(0.0, abs=1e-9)
    assert 0.5 * (bmin[0] + bmax[0]) == pytest.approx(0.0, abs=1e-9)
    assert 0.5 * (bmin[2] + bmax[2]) == pytest.approx(0.0, abs=1e-9)

    assert extents[0] == pytest.approx(0.85, abs=0.001)
    assert extents[1] == pytest.approx(0.78, abs=0.001)
    assert extents[2] == pytest.approx(0.72, abs=0.001)
    assert report.max_dimension_error_m < 0.001
    assert report.bounding_box_m["min_y"] == 0.0


def test_cylinder_mesh_scales_to_target_meters() -> None:
    """A vertical cylinder mesh should match target diameter and height."""
    # trimesh cylinder defaults to Z-up; rotate to Y-up as standard glTF product.
    cyl = trimesh.creation.cylinder(radius=0.5, height=3.0, sections=32)
    rot_x = trimesh.transformations.rotation_matrix(-np.pi / 2.0, [1, 0, 0])
    cyl.apply_transform(rot_x)

    scaled, report = normalize_mesh_to_metric_scale(
        cyl,
        width_m=0.40,
        height_m=1.45,
        depth_m=0.40,
        scale_mode="exact_fit",
    )

    extents = scaled.extents
    assert scaled.bounds[0][1] == pytest.approx(0.0, abs=1e-9)
    assert extents[0] == pytest.approx(0.40, abs=0.001)
    assert extents[1] == pytest.approx(1.45, abs=0.001)
    assert extents[2] == pytest.approx(0.40, abs=0.001)
    assert report.max_dimension_error_m < 0.001


def test_asymmetric_mesh_and_uniform_modes() -> None:
    """Asymmetric meshes should center properly and preserve aspect in uniform modes."""
    base = trimesh.creation.box(extents=[2.0, 1.0, 2.0])
    tower = trimesh.creation.box(extents=[0.5, 3.0, 0.5])
    tower.apply_translation([0.75, 1.5, -0.75])
    asymmetric = trimesh.util.concatenate([base, tower])

    # Exact fit
    exact_mesh, exact_report = normalize_mesh_to_metric_scale(
        asymmetric,
        width_m=1.20,
        height_m=0.90,
        depth_m=0.60,
        scale_mode="exact_fit",
    )
    assert exact_mesh.bounds[0][1] == pytest.approx(0.0, abs=1e-9)
    assert exact_mesh.extents == pytest.approx([1.20, 0.90, 0.60], abs=0.001)
    assert exact_report.aspect_delta["max_scale_ratio_spread"] > 0.5

    # Uniform contain mode fits inside target without distorting proportions
    uniform_mesh, uniform_report = normalize_mesh_to_metric_scale(
        asymmetric,
        width_m=1.00,
        height_m=2.00,
        depth_m=0.50,
        scale_mode="uniform",
    )
    assert uniform_mesh.bounds[0][1] == pytest.approx(0.0, abs=1e-9)
    assert uniform_report.scale_factors["x"] == pytest.approx(uniform_report.scale_factors["y"])
    assert uniform_report.scale_factors["y"] == pytest.approx(uniform_report.scale_factors["z"])
    assert uniform_mesh.extents[0] <= 1.00 + 1e-6
    assert uniform_mesh.extents[1] <= 2.00 + 1e-6
    assert uniform_mesh.extents[2] == pytest.approx(0.50, abs=0.001)

    # Uniform height mode
    uh_mesh, uh_report = normalize_mesh_to_metric_scale(
        asymmetric,
        width_m=1.00,
        height_m=1.40,
        depth_m=1.00,
        scale_mode="uniform_height",
    )
    assert uh_mesh.extents[1] == pytest.approx(1.40, abs=0.001)
    assert uh_report.scale_factors["x"] == pytest.approx(uh_report.scale_factors["y"])


def test_glb_export_roundtrip_preserves_metric_scale_and_extras(tmp_path: Path) -> None:
    """Exporting to .glb and reloading should keep < 1 mm precision and metadata."""
    mesh = trimesh.creation.box(extents=[3.0, 2.0, 4.0])
    scaled, report = normalize_mesh_to_metric_scale(
        mesh,
        width_m=0.75,
        height_m=0.82,
        depth_m=0.68,
        scale_mode="exact_fit",
        unit_input="cm",
    )

    glb_path = tmp_path / "scaled_box.glb"
    export_scaled_glb(scaled, glb_path, report=report)
    assert glb_path.exists() and glb_path.stat().st_size > 0

    reloaded = trimesh.load(glb_path)
    assert isinstance(reloaded, trimesh.Scene)
    bmin, bmax = reloaded.bounds
    extents = bmax - bmin
    assert bmin[1] == pytest.approx(0.0, abs=1e-5)
    assert extents[0] == pytest.approx(0.75, abs=0.001)
    assert extents[1] == pytest.approx(0.82, abs=0.001)
    assert extents[2] == pytest.approx(0.68, abs=0.001)
    assert "truescale" in reloaded.metadata
    assert reloaded.metadata["truescale"]["target_dimensions_m"]["height"] == 0.82
