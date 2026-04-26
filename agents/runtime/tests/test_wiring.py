"""Tests for the real-crew wiring (WS-401 follow-up).

Two flavors:

1. **Unit** — exercise ``register_real_crews()``'s import-failure path
   with module-level mocking. Always runs.
2. **Integration** — actually swap and drive the full blue → red → white
   chain through the harness. Skipped when any of the three crew
   packages isn't importable (so the runtime can be tested in
   isolation).
"""

from __future__ import annotations

import importlib
import os
import sys
from uuid import uuid4

import pytest

from almighty_agent_runtime import register_noop_crews, register_real_crews
from almighty_agent_runtime import crews as crews_mod


# Detect whether the integration path is available in this venv.
_BLUE_AVAIL = importlib.util.find_spec("almighty_blue_crew") is not None
_RED_AVAIL = importlib.util.find_spec("almighty_red_crew") is not None
_WHITE_AVAIL = importlib.util.find_spec("almighty_white_cell") is not None
_ALL_AVAIL = _BLUE_AVAIL and _RED_AVAIL and _WHITE_AVAIL


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------


def test_register_real_crews_returns_set_of_wired_sides(monkeypatch):
    """When importlib.import_module fails for a side, that side stays
    on its existing stub and is NOT in the returned set."""
    register_noop_crews()

    real = importlib.import_module
    blocked = {"almighty_blue_crew", "almighty_red_crew", "almighty_white_cell"}

    def stub_import(name, *args, **kwargs):
        if name in blocked:
            raise ImportError(f"blocked for test: {name}")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", stub_import)
    wired = register_real_crews()
    assert wired == set()


def test_register_noop_crews_is_idempotent_and_resets_slots():
    register_noop_crews()
    blue_before = crews_mod.BLUE_CREWS["default"]
    register_noop_crews()
    blue_after = crews_mod.BLUE_CREWS["default"]
    # Different closures (re-built), but both are stubs — calling them
    # produces the canonical "noop crew" notes.
    from almighty_agent_runtime.crews import CrewContext

    out = blue_after(CrewContext(tenant_id=str(uuid4()), scenario_id=str(uuid4()), turn=0))
    assert "noop" in out.notes.lower()
    assert blue_before is not blue_after  # rebuilt, not aliased


# ---------------------------------------------------------------------------
# Integration — only when all three crew packages are installed.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _ALL_AVAIL,
    reason="real crew packages (blue/red/white-cell) not installed",
)
def test_register_real_crews_swaps_all_three_when_available():
    register_noop_crews()
    wired = register_real_crews()
    assert wired == {"blue", "red", "white"}

    from almighty_agent_runtime.crews import CrewContext, _noop_crew_runner  # type: ignore

    # The slots no longer reference noop_crew_runner closures.
    blue_runner = crews_mod.BLUE_CREWS["default"]
    red_runner = crews_mod.RED_CREWS["default"]
    white_runner = crews_mod.WHITE_CREWS["default"]

    # Sanity: each runner is callable and returns a CrewResult with the
    # right `crew` field. We do NOT inspect events_committed here — the
    # detailed assertions live in each crew's own test suite.
    ctx = CrewContext(
        tenant_id="11111111-1111-4111-8111-111111111111",
        scenario_id="22222222-2222-4222-8222-222222222222",
        turn=0,
    )
    assert blue_runner(ctx).crew == "blue"
    assert red_runner(ctx).crew == "red"
    assert white_runner(ctx).crew == "white"


@pytest.mark.skipif(
    not _ALL_AVAIL,
    reason="real crew packages (blue/red/white-cell) not installed",
)
def test_full_chain_runs_real_crews_end_to_end(httpx_mock):
    """The DoD-equivalent for the wired path: the harness's chain runs
    real crews in sequence and produces a successful AsyncResult."""
    from almighty_agent_runtime import enqueue_turn

    tenant_id = str(uuid4())
    scenario_id = str(uuid4())
    cp_url = "http://control-plane.test"

    os.environ["ALMIGHTY_WORKER_TENANT_ID"] = tenant_id
    os.environ["CONTROL_PLANE_URL"] = cp_url

    # Each crew posts to its own /done URL.
    for crew in ("blue", "red", "white"):
        httpx_mock.add_response(
            method="POST",
            url=(
                f"{cp_url}/tenants/{tenant_id}"
                f"/scenarios/{scenario_id}"
                f"/turns/0"
                f"/crews/{crew}/done"
            ),
            json={"ok": True},
        )

    register_real_crews()
    try:
        result = enqueue_turn(
            tenant_id=tenant_id, scenario_id=scenario_id, turn=0
        )
        payload = result.get(timeout=30.0)
    finally:
        register_noop_crews()

    assert result.successful()
    assert payload["tenant_id"] == tenant_id
    assert payload["scenario_id"] == scenario_id
    assert payload["turn"] == 0

    # All three callbacks fired.
    requests = httpx_mock.get_requests()
    crews_called = {req.url.path.rsplit("/", 2)[-2] for req in requests}
    assert crews_called == {"blue", "red", "white"}


# ---------------------------------------------------------------------------
# Cleanup — make sure later tests in the same session see the noop default.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _restore_noop_after_test():
    yield
    register_noop_crews()
