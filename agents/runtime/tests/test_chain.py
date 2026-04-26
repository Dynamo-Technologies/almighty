"""Sequential ordering: blue -> red -> white."""

from __future__ import annotations

import os
from uuid import uuid4

from almighty_agent_runtime import enqueue_turn
from almighty_agent_runtime import crews as crews_mod


def test_chain_runs_blue_red_white_in_order(httpx_mock):
    """Patch each crew runner to record an ordering and assert it."""
    tenant_id = str(uuid4())
    scenario_id = str(uuid4())
    cp_url = "http://control-plane.test"
    os.environ["ALMIGHTY_WORKER_TENANT_ID"] = tenant_id
    os.environ["CONTROL_PLANE_URL"] = cp_url

    for crew in ("blue", "red", "white"):
        httpx_mock.add_response(
            method="POST",
            url=(
                f"{cp_url}/tenants/{tenant_id}"
                f"/scenarios/{scenario_id}/turns/0"
                f"/crews/{crew}/done"
            ),
            json={"ok": True},
        )

    order: list[str] = []

    def make_recorder(name: str):
        def _run(ctx):
            order.append(name)
            return crews_mod.CrewResult(crew=name, duration_ms=0)  # type: ignore[arg-type]

        return _run

    saved = {
        "blue": crews_mod.BLUE_CREWS["default"],
        "red": crews_mod.RED_CREWS["default"],
        "white": crews_mod.WHITE_CREWS["default"],
    }
    crews_mod.BLUE_CREWS["default"] = make_recorder("blue")
    crews_mod.RED_CREWS["default"] = make_recorder("red")
    crews_mod.WHITE_CREWS["default"] = make_recorder("white")

    try:
        result = enqueue_turn(
            tenant_id=tenant_id, scenario_id=scenario_id, turn=0
        )
        result.get(timeout=2.0)
    finally:
        crews_mod.BLUE_CREWS["default"] = saved["blue"]
        crews_mod.RED_CREWS["default"] = saved["red"]
        crews_mod.WHITE_CREWS["default"] = saved["white"]

    assert order == ["blue", "red", "white"]


def test_callback_endpoint_404_does_not_break_chain(httpx_mock):
    """Simulate the control plane endpoint not yet existing (per WS-302
    follow-up). Crew tasks should soft-fail the callback and continue
    so dev iteration isn't blocked.
    """
    tenant_id = str(uuid4())
    scenario_id = str(uuid4())
    cp_url = "http://control-plane.test"
    os.environ["ALMIGHTY_WORKER_TENANT_ID"] = tenant_id
    os.environ["CONTROL_PLANE_URL"] = cp_url

    for crew in ("blue", "red", "white"):
        httpx_mock.add_response(
            method="POST",
            url=(
                f"{cp_url}/tenants/{tenant_id}"
                f"/scenarios/{scenario_id}/turns/7"
                f"/crews/{crew}/done"
            ),
            status_code=404,
        )

    result = enqueue_turn(
        tenant_id=tenant_id, scenario_id=scenario_id, turn=7
    )
    payload = result.get(timeout=2.0)
    assert payload["turn"] == 7
    assert result.successful()
