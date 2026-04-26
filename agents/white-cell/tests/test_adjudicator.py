"""Adjudicator decision tests — covers WS-405 DoD."""

from __future__ import annotations

from uuid import uuid4

from almighty_white_cell import Decision, adjudicate_events

from conftest import make_event


def test_low_stakes_event_auto_approves():
    e = make_event(action_verb="detect", source_officer_type="SENSOR")
    [d] = adjudicate_events([e])
    assert isinstance(d, Decision)
    assert d.stake == "low"
    assert d.outcome == "auto-approve"
    assert d.human_required is False


def test_destroy_event_holds_for_human_ack():
    """DoD: high-stakes path requires human ack."""
    e = make_event(
        action_verb="destroy",
        source_officer_type="EFFECTOR",
        payload={
            "target_entity_id": str(uuid4()),
            "weapon_system": "notional.indirect.medium",
            "stake": "high",
        },
    )
    [d] = adjudicate_events([e])
    assert d.stake == "high"
    assert d.outcome == "review-pending"
    assert d.human_required is True
    assert "human ack" in d.rationale


def test_contested_pair_resolves_to_one_decision_each():
    """DoD: contested-effect scenario fixture — feed blue/red event
    pair where outcomes differ; adjudicator produces one
    proposed_resolution per event (not one merged)."""
    target = str(uuid4())
    blue = make_event(
        action_verb="engage",
        source_officer_type="EFFECTOR",
        payload={"target_entity_id": target, "intent": "NEUTRALIZE"},
    )
    red = make_event(
        action_verb="engage",
        source_officer_type="EFFECTOR",
        payload={"target_entity_id": target, "intent": "SUPPRESS_AND_HOLD"},
    )
    decisions = adjudicate_events([blue, red])
    assert len(decisions) == 2
    for d in decisions:
        assert d.contested is True
        assert "contested" in d.rationale
    # Each conflicts with the other.
    assert decisions[0].conflicts_with == [red.event_id]
    assert decisions[1].conflicts_with == [blue.event_id]


def test_contested_marker_in_payload_triggers():
    """Caller-set payload marker forces contested even without
    target overlap."""
    e = make_event(
        action_verb="send",
        source_officer_type="COMMUNICATOR",
        payload={"contested": True},
    )
    [d] = adjudicate_events([e])
    assert d.contested is True


def test_high_stakes_AND_contested_still_holds_for_human():
    """An event that is both high-stakes AND contested still routes to
    review-pending (human ack), not to auto-approve."""
    target = str(uuid4())
    other = make_event(
        action_verb="engage",
        source_officer_type="EFFECTOR",
        payload={"target_entity_id": target},
    )
    destroy = make_event(
        action_verb="destroy",
        source_officer_type="EFFECTOR",
        payload={"target_entity_id": target, "stake": "high"},
    )
    decisions = adjudicate_events([destroy, other])
    destroy_decision = next(d for d in decisions if d.action_verb == "destroy")
    assert destroy_decision.stake == "high"
    assert destroy_decision.outcome == "review-pending"
    assert destroy_decision.human_required is True
    assert destroy_decision.contested is True
    assert "contested" in destroy_decision.rationale


def test_custom_stake_predicate_overrides_default():
    """Caller-supplied predicate is honored for scenario-specific policy."""
    e = make_event(action_verb="send", source_officer_type="COMMUNICATOR")
    decisions = adjudicate_events(
        [e],
        stake_predicate=lambda _e: "high",
    )
    assert decisions[0].stake == "high"
    assert decisions[0].human_required is True


def test_decision_order_matches_event_order():
    a = make_event(action_verb="detect", source_officer_type="SENSOR")
    b = make_event(action_verb="move_to", source_officer_type="MOVER")
    c = make_event(action_verb="send", source_officer_type="COMMUNICATOR")
    decisions = adjudicate_events([a, b, c])
    assert [d.event_id for d in decisions] == [a.event_id, b.event_id, c.event_id]
