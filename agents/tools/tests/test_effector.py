"""Tests for the four Effector verbs."""

from __future__ import annotations

from uuid import uuid4

import pytest

from almighty_officer_tools import ToolError


def test_engage_happy(all_tools_us_bct):
    out = all_tools_us_bct["engage"]._run(
        target_entity_id=uuid4(),
        weapon_system="notional.indirect.medium",
        volume_count=4,
        intent="NEUTRALIZE",
        range_m=10_000.0,
        time_of_flight_s=25.0,
    )
    assert out["verb"] == "engage"
    assert out["validator"] == "accepted"


def test_engage_out_of_range_rejects(all_tools_us_bct):
    """us-bct indirect_fire_arc.range_m max is 25000; 50000 must reject."""
    with pytest.raises(ToolError) as exc:
        all_tools_us_bct["engage"]._run(
            target_entity_id=uuid4(),
            weapon_system="notional.indirect.medium",
            volume_count=1,
            range_m=50_000.0,
            time_of_flight_s=25.0,
        )
    assert "validator rejected 'engage'" in exc.value.reason
    assert "range_m" in exc.value.reason


def test_suppress_happy(all_tools_us_bct):
    out = all_tools_us_bct["suppress"]._run(
        weapon_system="notional.indirect.medium",
        duration_s=120.0,
        rate_per_min=4.0,
        target_lat_deg=36.18,
        target_lon_deg=-86.78,
        range_m=8_000.0,
        time_of_flight_s=20.0,
    )
    assert out["validator"] == "accepted"


def test_destroy_carries_high_stake(all_tools_us_bct, kernel_dag):
    out = all_tools_us_bct["destroy"]._run(
        target_entity_id=uuid4(),
        weapon_system="notional.indirect.medium",
        volume_count=2,
        justification="confirmed enemy command vehicle, no civilians within 500 m",
        range_m=12_000.0,
        time_of_flight_s=30.0,
    )
    assert out["verb"] == "destroy"
    assert out["validator"] == "accepted"
    # The committed event payload should carry the stake marker the
    # adjudicator (WS-405) reads.
    events = list(kernel_dag._index.values())
    # The committed event is the one we just added; assert at least one
    # destroy event exists with stake='high'.
    payload_stakes = [
        e.payload.get("stake")
        for _, e in events
        if e.name == "destroy"
    ]
    assert "high" in payload_stakes


def test_disable_kinetic_uses_indirect_fire(all_tools_peer):
    """peer.json has 'disable' verb. KINETIC method routes to indirect_fire_arc."""
    out = all_tools_peer["disable"]._run(
        target_entity_id=uuid4(),
        method="KINETIC",
        weapon_system="notional.indirect.medium",
        range_m=8_000.0,
        time_of_flight_s=20.0,
    )
    assert out["validator"] == "accepted"


def test_disable_cyber_no_validator(all_tools_peer):
    """CYBER method -> no spatial artifact -> validator skipped."""
    out = all_tools_peer["disable"]._run(
        target_entity_id=uuid4(),
        method="CYBER",
        weapon_system="notional.cyber.placeholder",
    )
    assert out["validator"] == "skipped"


def test_us_bct_lacks_disable_verb(us_bct_profile, all_tools_us_bct):
    """Confirm capability gate fires when profile lacks the verb."""
    assert "disable" not in us_bct_profile["action_verbs_available"]
    with pytest.raises(ToolError) as exc:
        all_tools_us_bct["disable"]._run(
            target_entity_id=uuid4(),
            method="KINETIC",
            weapon_system="notional.indirect.medium",
        )
    assert "capability gate" in exc.value.reason
