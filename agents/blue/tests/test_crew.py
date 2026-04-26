"""End-to-end test for the v1 deterministic blue crew (WS-403 DoD).

The DoD: "crew runs one full between-turn cycle producing valid
PyRapide events." This test runs ``run_blue_crew`` once and asserts:

  - The crew completes (no ToolError raised).
  - Every step's tool call was accepted (validator rejections == 0;
    capability-gate misses would raise ToolError before reaching here).
  - The KernelEvents produced cover all six roles' verbs in the
    expected officer-type distribution.
  - No two events share an event_id (UUID v4 collision sanity).
"""

from __future__ import annotations

from almighty_blue_crew.crew import _BETWEEN_TURN_SCRIPT, run_blue_crew


def test_crew_runs_one_full_cycle(crew_ctx):
    result = run_blue_crew(crew_ctx)
    assert result.crew == "blue"
    assert result.duration_ms >= 0
    assert result.metadata["events_committed"] == len(_BETWEEN_TURN_SCRIPT)
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
    """Six roles contribute to the run; the officer-type mix should
    reflect the WS-105 verb-to-officer mapping."""
    result = run_blue_crew(crew_ctx)
    types = [step["officer_type"] for step in result.metadata["steps"]]
    counts = {t: types.count(t) for t in set(types)}
    # Sensor (S2): 2 events (detect + classify).
    assert counts.get("SENSOR") == 2
    # Commander (S3): 2 events (issue_order + request_support).
    assert counts.get("COMMANDER") == 2
    # Mover: 3 events (CO A assume_posture, CO B halt, CO C move_to).
    assert counts.get("MOVER") == 3
    # Effector: 1 event (CO B suppress).
    assert counts.get("EFFECTOR") == 1
    # Communicator: 3 events (CO A send + S6 send + S6 report).
    assert counts.get("COMMUNICATOR") == 3
    assert sum(counts.values()) == len(_BETWEEN_TURN_SCRIPT)


def test_every_step_validator_field_set(crew_ctx):
    """Every step result must declare validator outcome — 'accepted' for
    CZML-emitting steps (Sensor.classify, Effector.suppress) and
    'skipped' for non-spatial steps."""
    result = run_blue_crew(crew_ctx)
    accepted_or_skipped = {step["validator"] for step in result.metadata["steps"]}
    assert accepted_or_skipped <= {"accepted", "skipped"}
    # At least one accepted (means we exercised the validator path).
    assert "accepted" in accepted_or_skipped


def test_runner_export_is_callable(crew_ctx):
    from almighty_blue_crew import BLUE_RUNNER

    out = BLUE_RUNNER(crew_ctx)
    assert out.crew == "blue"
    assert out.metadata["events_committed"] == len(_BETWEEN_TURN_SCRIPT)
