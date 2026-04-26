"""Shared fixtures for the red-crew tests."""

from __future__ import annotations

import pytest

from almighty_agent_runtime.crews import CrewContext


@pytest.fixture()
def crew_ctx() -> CrewContext:
    return CrewContext(
        tenant_id="11111111-1111-4111-8111-111111111111",
        scenario_id="22222222-2222-4222-8222-222222222222",
        turn=1,
    )
