"""HTTP-layer smoke tests for the FastAPI app."""

from __future__ import annotations

from fastapi.testclient import TestClient

from almighty_czml_validator.app import app


client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_validate_endpoint_accept(profiles):
    profile = profiles["us-bct"]
    body = {
        "template_id": "indirect-fire-arc",
        "template_version": 1,
        "params": {
            "range_m": 10000,
            "time_of_flight_s": 25,
            "dispersion_ellipse_a_m": 50,
            "dispersion_ellipse_b_m": 50,
        },
        "agent_id": "test-http-agent",
        "capability_profile": profile,
    }
    r = client.post("/validate", json=body)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["accepted"] is True
    assert payload["reasons"] == []


def test_validate_endpoint_reject(profiles):
    profile = profiles["us-bct"]
    body = {
        "template_id": "jamming-circle",
        "params": {"radius_m": 500, "power_w": 100},
        "agent_id": "test-http-agent",
        "capability_profile": profile,
    }
    r = client.post("/validate", json=body)
    assert r.status_code == 200
    payload = r.json()
    assert payload["accepted"] is False
    assert "no verb that emits family 'jamming_circle'" in payload["reasons"][0]
