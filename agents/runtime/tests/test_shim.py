"""Tests for the FastAPI shim that wraps run_blue_crew + run_red_crew.

The shim is what the EC2 control-plane POSTs to over Tailscale. The
heavy lifting (LLM calls, kernel commits) lives in the crew code; the
shim's job is parallelizing the two crews, gathering their step
outcomes, and returning a JSON list of events.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _fake_crew_result(crew: str, steps: list[dict]):
    """Mirror the shape of CrewResult that the real crew runners return."""
    return SimpleNamespace(
        crew=crew,
        duration_ms=42,
        notes="(test stub)",
        metadata={
            "tenant_id": "00000000-0000-4d00-8000-000000000001",
            "scenario_id": "00000000-0000-4101-8000-000000000001",
            "turn": 1,
            "events_committed": len(steps),
            "steps": steps,
            "validator_rejections": 0,
        },
    )


@pytest.fixture()
def client():
    from almighty_agent_runtime.shim import app
    return TestClient(app)


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_run_turn_invokes_both_crews_and_returns_events(client):
    blue_steps = [
        {"step": "s2.detect", "event_id": "ev-blue-1", "verb": "detect",
         "officer_type": "SENSOR", "validator": "skipped",
         "causal_predecessors": []},
        {"step": "s3.llm_decide.issue_order", "event_id": "ev-blue-2", "verb": "issue_order",
         "officer_type": "COMMANDER", "validator": "skipped",
         "causal_predecessors": ["ev-blue-1"], "llm_driven": True},
    ]
    red_steps = [
        {"step": "s2.detect", "event_id": "ev-red-1", "verb": "detect",
         "officer_type": "SENSOR", "validator": "skipped",
         "causal_predecessors": []},
    ]

    blue_mock = MagicMock(return_value=_fake_crew_result("blue", blue_steps))
    red_mock = MagicMock(return_value=_fake_crew_result("red", red_steps))

    with patch("almighty_agent_runtime.shim.run_blue_crew", blue_mock), \
         patch("almighty_agent_runtime.shim.run_red_crew", red_mock):
        r = client.post("/run-turn", json={
            "tenant_id": "00000000-0000-4d00-8000-000000000001",
            "scenario_id": "00000000-0000-4101-8000-000000000001",
            "turn": 1,
        })

    assert r.status_code == 200
    body = r.json()
    assert body["turn"] == 1
    assert body["blue_duration_ms"] == 42
    assert body["red_duration_ms"] == 42
    # 2 blue events + 1 red event = 3 total
    assert len(body["events"]) == 3
    sides = {e["side"] for e in body["events"]}
    assert sides == {"blue", "red"}
    # Causal predecessors round-trip through the wire
    chained = [e for e in body["events"] if e["causal_predecessors"]]
    assert len(chained) == 1
    assert chained[0]["causal_predecessors"] == ["ev-blue-1"]
    assert chained[0]["verb"] == "issue_order"
    # Tenant/scenario stamped on every event
    for e in body["events"]:
        assert e["tenant_id"] == "00000000-0000-4d00-8000-000000000001"
        assert e["scenario_id"] == "00000000-0000-4101-8000-000000000001"
        assert e["turn"] == 1


def test_run_turn_runs_crews_concurrently(client):
    """Both crews are dispatched without blocking each other. We can't
    measure real wall clock here, but we can assert the two mocks were
    called within the same handler invocation."""
    call_order = []

    def make_mock(name):
        def _crew(ctx):
            call_order.append(("start", name))
            call_order.append(("end", name))
            return _fake_crew_result(name, [])
        return MagicMock(side_effect=_crew)

    with patch("almighty_agent_runtime.shim.run_blue_crew", make_mock("blue")), \
         patch("almighty_agent_runtime.shim.run_red_crew", make_mock("red")):
        r = client.post("/run-turn", json={
            "tenant_id": "00000000-0000-4d00-8000-000000000001",
            "scenario_id": "00000000-0000-4101-8000-000000000001",
            "turn": 1,
        })

    assert r.status_code == 200
    starts = [n for kind, n in call_order if kind == "start"]
    assert set(starts) == {"blue", "red"}


def test_run_turn_rejects_invalid_payload(client):
    r = client.post("/run-turn", json={"turn": 1})  # missing tenant/scenario
    assert r.status_code == 422
