"""Stake classification tests."""

from __future__ import annotations

from almighty_white_cell import stake_level

from conftest import make_event


def test_destroy_is_always_high():
    e = make_event(
        action_verb="destroy",
        source_officer_type="EFFECTOR",
        payload={"target_entity_id": "00000000-0000-4000-8000-000000000000"},
    )
    assert stake_level(e) == "high"


def test_explicit_stake_marker_escalates():
    """Even a non-destroy verb escalates when payload.stake='high' is
    stamped (e.g., by a v2 tool)."""
    e = make_event(
        action_verb="engage",
        source_officer_type="EFFECTOR",
        payload={"stake": "high"},
    )
    assert stake_level(e) == "high"


def test_engage_against_neutral_is_high():
    e = make_event(
        action_verb="engage",
        source_officer_type="EFFECTOR",
        payload={"target_force_affiliation": "NEUTRAL"},
    )
    assert stake_level(e) == "high"


def test_disable_against_civilian_is_high():
    e = make_event(
        action_verb="disable",
        source_officer_type="EFFECTOR",
        payload={"target_is_civilian": True, "method": "KINETIC"},
    )
    assert stake_level(e) == "high"


def test_jam_with_civilian_band_overlap_is_high():
    e = make_event(
        action_verb="jam",
        source_officer_type="COMMUNICATOR",
        payload={"civilian_band_overlap": True, "band": "VHF"},
    )
    assert stake_level(e) == "high"


def test_engage_routine_is_medium():
    e = make_event(
        action_verb="engage",
        source_officer_type="EFFECTOR",
        payload={"weapon_system": "notional.indirect.medium"},
    )
    assert stake_level(e) == "medium"


def test_suppress_is_medium():
    e = make_event(action_verb="suppress", source_officer_type="EFFECTOR")
    assert stake_level(e) == "medium"


def test_jam_routine_is_medium():
    e = make_event(
        action_verb="jam",
        source_officer_type="COMMUNICATOR",
        payload={"band": "L"},
    )
    assert stake_level(e) == "medium"


def test_detect_is_low():
    e = make_event(
        action_verb="detect",
        source_officer_type="SENSOR",
        payload={"modality": "RADAR"},
    )
    assert stake_level(e) == "low"


def test_move_to_is_low():
    e = make_event(action_verb="move_to", source_officer_type="MOVER")
    assert stake_level(e) == "low"


def test_send_is_low():
    e = make_event(action_verb="send", source_officer_type="COMMUNICATOR")
    assert stake_level(e) == "low"


def test_issue_order_is_low():
    e = make_event(action_verb="issue_order", source_officer_type="COMMANDER")
    assert stake_level(e) == "low"
