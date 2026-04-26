"""End-to-end tests for the blue crew (WS-403 + hackathon-demo flip).

The S3 step is now LLM-driven. The conftest's autouse `_disable_llm_in_tests`
fixture patches `build_blue_llm` to raise so the deterministic fallback
runs in CI — that path commits exactly the same two S3 events the v1
script committed (issue_order + request_support), preserving the v1
event-count and officer-type invariants.
"""

from __future__ import annotations

from almighty_blue_crew.crew import _BETWEEN_TURN_SCRIPT, run_blue_crew

# Number of events committed in fallback mode (S3 fallback expands the
# single script entry into the same two events the v1 script committed).
_FALLBACK_EVENT_COUNT = 11
# Number of script entries — one less than the v1 11 because the two
# S3 deterministic steps are unified under _step_s3_llm_decide.
_SCRIPT_ENTRY_COUNT = 10


def test_script_has_one_unified_s3_entry():
    labels = [label for label, _ in _BETWEEN_TURN_SCRIPT]
    assert "s3.llm_decide" in labels
    assert "s3.issue_order" not in labels
    assert "s3.request_support" not in labels
    assert len(_BETWEEN_TURN_SCRIPT) == _SCRIPT_ENTRY_COUNT


def test_crew_runs_one_full_cycle(crew_ctx):
    result = run_blue_crew(crew_ctx)
    assert result.crew == "blue"
    assert result.duration_ms >= 0
    # Fallback mode (forced by conftest): 11 events from 10 script entries
    # because the s3.llm_decide entry expands to two deterministic commits.
    assert result.metadata["events_committed"] == _FALLBACK_EVENT_COUNT
    assert result.metadata["validator_rejections"] == 0
    assert result.metadata["tenant_id"] == crew_ctx.tenant_id
    assert result.metadata["scenario_id"] == crew_ctx.scenario_id
    assert result.metadata["turn"] == crew_ctx.turn


def test_every_step_has_an_event_id(crew_ctx):
    result = run_blue_crew(crew_ctx)
    event_ids = [step["event_id"] for step in result.metadata["steps"]]
    assert len(event_ids) == len(set(event_ids)), "step event_ids must be unique"
    assert all(eid for eid in event_ids), "every step must produce an event_id"


def test_officer_type_distribution(crew_ctx):
    """Six roles contribute to the run; the officer-type mix matches
    the v1 verb-to-officer mapping (fallback mode preserves it)."""
    result = run_blue_crew(crew_ctx)
    types = [step["officer_type"] for step in result.metadata["steps"]]
    counts = {t: types.count(t) for t in set(types)}
    assert counts.get("SENSOR") == 2  # S2 detect + classify
    assert counts.get("COMMANDER") == 2  # S3 issue_order + request_support (fallback)
    assert counts.get("MOVER") == 3  # CO A posture, CO B halt, CO C move
    assert counts.get("EFFECTOR") == 1  # CO B suppress
    assert counts.get("COMMUNICATOR") == 3  # CO A send + S6 send + S6 report
    assert sum(counts.values()) == _FALLBACK_EVENT_COUNT


def test_every_step_validator_field_set(crew_ctx):
    """Every step result declares validator outcome — 'accepted' for
    CZML-emitting steps and 'skipped' for non-spatial steps."""
    result = run_blue_crew(crew_ctx)
    accepted_or_skipped = {step["validator"] for step in result.metadata["steps"]}
    assert accepted_or_skipped <= {"accepted", "skipped"}
    assert "accepted" in accepted_or_skipped


def test_runner_export_is_callable(crew_ctx):
    from almighty_blue_crew import BLUE_RUNNER

    out = BLUE_RUNNER(crew_ctx)
    assert out.crew == "blue"
    assert out.metadata["events_committed"] == _FALLBACK_EVENT_COUNT


def test_fallback_step_records_reason(crew_ctx):
    """The conftest forces fallback. The two S3 steps in the resulting
    outcomes carry llm_driven=False and a fallback_reason — that's the
    audit trail the demo's recovery line depends on."""
    result = run_blue_crew(crew_ctx)
    s3_steps = [s for s in result.metadata["steps"] if s["step"].startswith("s3.")]
    assert len(s3_steps) == 2
    for s in s3_steps:
        assert s["llm_driven"] is False
        assert "LLM disabled in unit tests" in s["fallback_reason"]
