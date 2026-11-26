"""Tests for backend health check endpoint and configuration."""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402


def test_health_check_returns_ok() -> None:
    """GET /api/health should report status ok and ready local storage."""
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["default_engine"] == "local_cpu"
    assert payload["storage_ready"] is True
    assert "version" in payload
