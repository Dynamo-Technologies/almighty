"""Test fixtures.

Existing tests in this package rely on `run_blue_crew` producing the
deterministic v1 event sequence. After the hackathon-demo flip
(`_step_s3_llm_decide`), the crew tries to call Gemma on spark-763d
unless we short-circuit. The auto-applied fixture below patches
`build_blue_llm` to raise so the LLM-step's deterministic fallback
runs in CI — same behavior the v1 tests covered.

Tests that specifically want to exercise the LLM-mode path can
override the fixture or patch differently.
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
    """Force the LLM-driven S3 step into deterministic fallback so the
    test suite doesn't try to reach Gemma on the Sparks. Tests that want
    to exercise the LLM path mock `run_llm_role_step` instead."""
    with patch(
        "almighty_blue_crew.crew.build_blue_llm",
        side_effect=RuntimeError("LLM disabled in unit tests"),
    ):
        yield
