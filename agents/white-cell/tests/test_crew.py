"""End-to-end tests for the white-cell crew runner."""

from __future__ import annotations

from almighty_white_cell import run_white_crew


def test_crew_runs_and_returns_per_event_decisions(crew_ctx):
    result = run_white_crew(crew_ctx)
    assert result.crew == "white"
    # Synthetic event batch is 6 events (3 routine + 2 contested + 1 destroy).
    assert result.metadata["events_in"] == 6
    assert len(result.metadata["decisions"]) == 6
    assert result.duration_ms >= 0
    assert result.metadata["tenant_id"] == crew_ctx.tenant_id
    assert result.metadata["scenario_id"] == crew_ctx.scenario_id
    assert result.metadata["turn"] == crew_ctx.turn


def test_crew_holds_destroy_for_human_ack(crew_ctx):
    """DoD: synthetic destroy event → human_required=true; gateway
    state confirmed held (we assert outcome='review-pending' as the
    gateway-state proxy)."""
    result = run_white_crew(crew_ctx)
    destroy_decisions = [
        d for d in result.metadata["decisions"] if d["action_verb"] == "destroy"
    ]
    assert len(destroy_decisions) == 1
    d = destroy_decisions[0]
    assert d["stake"] == "high"
    assert d["outcome"] == "review-pending"
    assert d["human_required"] is True


def test_crew_resolves_contested_pair(crew_ctx):
    """DoD: contested-effect scenario — both engage events on the
    shared target are flagged contested with mutual conflicts_with
    references."""
    result = run_white_crew(crew_ctx)
    engage_decisions = [
        d for d in result.metadata["decisions"] if d["action_verb"] == "engage"
    ]
    assert len(engage_decisions) == 2
    for d in engage_decisions:
        assert d["contested"] is True
        assert len(d["conflicts_with"]) == 1
    assert engage_decisions[0]["conflicts_with"] == [engage_decisions[1]["event_id"]]
    assert engage_decisions[1]["conflicts_with"] == [engage_decisions[0]["event_id"]]


def test_crew_auto_approves_routine_events(crew_ctx):
    """The 3 routine events (detect / move_to / send) auto-approve."""
    result = run_white_crew(crew_ctx)
    routine = [
        d
        for d in result.metadata["decisions"]
        if d["action_verb"] in ("detect", "move_to", "send")
    ]
    assert len(routine) == 3
    for d in routine:
        assert d["stake"] == "low"
        assert d["outcome"] == "auto-approve"
        assert d["human_required"] is False


def test_crew_notes_summary_string(crew_ctx):
    """The notes string reports the held-for-human count."""
    result = run_white_crew(crew_ctx)
    held = sum(1 for d in result.metadata["decisions"] if d["human_required"])
    assert held >= 1
    assert f"{held} held for human ack" in result.notes


def test_runner_export_is_callable(crew_ctx):
    from almighty_white_cell import WHITE_RUNNER

    out = WHITE_RUNNER(crew_ctx)
    assert out.crew == "white"
    assert out.metadata["events_in"] == 6
