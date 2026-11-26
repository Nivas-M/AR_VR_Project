"""End-to-end API pipeline tests for catalog, job execution, and .glb scale."""

import io
import json
import sys
from pathlib import Path

import pytest
import trimesh
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402


def _png_bytes_for_box(color: tuple[int, int, int], rect: tuple[int, int, int, int]) -> bytes:
    """Create a synthetic studio PNG photo in memory."""
    img = Image.new("RGB", (240, 240), (245, 246, 248))
    draw = ImageDraw.Draw(img)
    draw.rectangle(list(rect), fill=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_catalog_endpoints_and_bundled_images() -> None:
    """GET /api/products and image endpoints should expose all 5 sample products."""
    with TestClient(app) as client:
        res = client.get("/api/products")
        assert res.status_code == 200
        body = res.json()
        assert body["count"] == 5
        ids = {item["id"] for item in body["products"]}
        assert "nordic-armchair" in ids
        assert "walnut-coffee-table" in ids

        detail = client.get("/api/products/nordic-armchair")
        assert detail.status_code == 200
        product = detail.json()
        assert product["dimensions_cm"] == {"width": 78.0, "height": 84.0, "depth": 74.0}
        assert len(product["images"]) == 4

        img_res = client.get(product["images"][0]["url"])
        assert img_res.status_code == 200
        assert img_res.headers["content-type"].startswith("image/png")

        missing = client.get("/api/products/does-not-exist")
        assert missing.status_code == 404


def test_uploaded_photos_reconstruct_to_exact_metric_glb(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uploaded multi-view photos should produce a downloadable .glb matching target meters."""
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")
    monkeypatch.setattr(settings, "voxel_resolution", 48)

    front_png = _png_bytes_for_box((42, 108, 136), (55, 40, 185, 205))
    side_png = _png_bytes_for_box((120, 82, 52), (70, 40, 170, 205))

    with TestClient(app) as client:
        resp = client.post(
            "/api/reconstruct",
            files=[
                ("files", ("front.png", front_png, "image/png")),
                ("files", ("side.png", side_png, "image/png")),
            ],
            data={
                "angles": json.dumps(["front", "side"]),
                "width": "85",
                "height": "78",
                "depth": "72",
                "unit": "cm",
                "scale_mode": "exact_fit",
                "engine": "local_cpu",
                "title": "Test Studio Chair",
            },
        )
        assert resp.status_code == 202
        queued = resp.json()
        job_id = queued["job_id"]
        model_id = queued["model_id"]

        job_resp = client.get(f"/api/jobs/{job_id}")
        assert job_resp.status_code == 200
        job = job_resp.json()
        assert job["status"] == "done"
        assert job["progress"] == 100
        assert job["model_url"] == f"/api/models/{model_id}.glb"
        assert job["scale_report"]["max_dimension_error_m"] < 0.001

        glb_resp = client.get(job["model_url"])
        assert glb_resp.status_code == 200
        assert glb_resp.headers["content-type"] == "model/gltf-binary"
        assert glb_resp.headers["access-control-allow-origin"] == "*"

        meta_resp = client.get(f"/api/models/{model_id}/meta")
        assert meta_resp.status_code == 200
        assert meta_resp.json()["title"] == "Test Studio Chair"

    scene = trimesh.load(io.BytesIO(glb_resp.content), file_type="glb")
    assert isinstance(scene, trimesh.Scene)
    bmin, bmax = scene.bounds
    extents = bmax - bmin
    assert bmin[1] == pytest.approx(0.0, abs=1e-5)
    assert extents[0] == pytest.approx(0.85, abs=0.001)
    assert extents[1] == pytest.approx(0.78, abs=0.001)
    assert extents[2] == pytest.approx(0.72, abs=0.001)


def test_catalog_product_reconstructs_end_to_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Submitting product_id alone should reconstruct from bundled PNGs at catalog dimensions."""
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")
    monkeypatch.setattr(settings, "voxel_resolution", 48)

    with TestClient(app) as client:
        resp = client.post(
            "/api/reconstruct",
            data={"product_id": "walnut-coffee-table", "engine": "local_cpu"},
        )
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]

        job = client.get(f"/api/jobs/{job_id}").json()
        assert job["status"] == "done"
        assert job["mesh_stats"]["view_count"] == 4

        glb_bytes = client.get(job["model_url"]).content

    scene = trimesh.load(io.BytesIO(glb_bytes), file_type="glb")
    assert scene.extents == pytest.approx([1.10, 0.45, 0.60], abs=0.001)


def test_api_validation_and_not_found_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """API should reject bad requests cleanly with 400/404 status codes."""
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")

    with TestClient(app) as client:
        # Missing both files and product_id
        assert client.post("/api/reconstruct", data={"width": "50"}).status_code == 400
        # Unknown engine
        assert (
            client.post("/api/reconstruct", data={"product_id": "nordic-armchair", "engine": "bad"}).status_code
            == 400
        )
        # Missing job / model
        assert client.get("/api/jobs/nonexistent").status_code == 404
        assert client.get("/api/models/nonexistent.glb").status_code == 404
