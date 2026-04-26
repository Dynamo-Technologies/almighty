"""WS-401 DoD: empty crew runs end-to-end and signals completion in < 2 s."""

from __future__ import annotations

import os
import time
from uuid import uuid4

import pytest

from almighty_agent_runtime import enqueue_turn


def test_empty_crew_chain_finishes_within_2s(httpx_mock):
    tenant_id = str(uuid4())
    scenario_id = str(uuid4())
    cp_url = "http://control-plane.test"

    os.environ["ALMIGHTY_WORKER_TENANT_ID"] = tenant_id
    os.environ["CONTROL_PLANE_URL"] = cp_url

    # Each crew posts to its own /done URL; mock all three.
    for crew in ("blue", "red", "white"):
        httpx_mock.add_response(
            method="POST",
            url=(
                f"{cp_url}/tenants/{tenant_id}"
                f"/scenarios/{scenario_id}"
                f"/turns/3"
                f"/crews/{crew}/done"
            ),
            json={"ok": True},
        )

    started = time.perf_counter()
    result = enqueue_turn(tenant_id=tenant_id, scenario_id=scenario_id, turn=3)
    elapsed = time.perf_counter() - started

    # In eager mode the chain has already executed by the time apply_async returns.
    assert result.successful()
    payload = result.get(timeout=2.0)
    assert payload["tenant_id"] == tenant_id
    assert payload["scenario_id"] == scenario_id
    assert payload["turn"] == 3

    # All three callbacks fired (blue + red + white).
    requests = httpx_mock.get_requests()
    assert len(requests) == 3
    crews_called = {req.url.path.rsplit("/", 2)[-2] for req in requests}
    assert crews_called == {"blue", "red", "white"}

    # < 2 s end-to-end.
    assert elapsed < 2.0, f"empty crew chain took {elapsed:.3f}s (>= 2.0s)"
