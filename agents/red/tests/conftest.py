"""Shared fixtures for the red-crew tests.

Existing tests rely on `run_red_crew` producing the deterministic v1
event sequence. After the hackathon-demo flip (`_step_red_s3_llm_decide`
for peer/near-peer doctrines), the crew tries to call Gemma on
spark-3fe3 unless we short-circuit. The auto-applied fixture below
patches `build_red_llm` to raise so the LLM-step's deterministic
fallback runs in CI.

Hybrid doctrine is unaffected (still uses _step_s3_send_shadow).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from almighty_agent_runtime.crews import CrewContext


@pytest.fixture()
def crew_ctx() -> CrewContext:
    return CrewContext(
        tenant_id="11111111-1111-4111-8111-111111111111",
        scenario_id="22222222-2222-4222-8222-222222222222",
        turn=1,
    )


@pytest.fixture(autouse=True)
def _disable_llm_in_tests():
    """Force LLM-driven red S3 into deterministic fallback in CI."""
    with patch(
        "almighty_red_crew.crew.build_red_llm",
        side_effect=RuntimeError("LLM disabled in unit tests"),
    ):
        yield
