"""HTTP-layer smoke for the FastAPI shell."""

from __future__ import annotations

from fastapi.testclient import TestClient

from almighty_czml_adapter.app import app

client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
