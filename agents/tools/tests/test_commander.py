"""Tests for the four Commander verbs."""

from __future__ import annotations

from uuid import uuid4

import pytest

from almighty_officer_tools import ToolError


def test_issue_order(all_tools_us_bct):
    out = all_tools_us_bct["issue_order"]._run(
        order_type="MOVE",
        order_payload={"waypoint": [36.20, -86.78]},
        to_echelon="COMPANY",
    )
    assert out["verb"] == "issue_order"
    assert out["validator"] == "skipped"


def test_request_support_fires_requires_coord(all_tools_us_bct):
    """FIRES support without target coord must fail at the args schema."""
    with pytest.raises(Exception):  # pydantic ValidationError surfaces here
        all_tools_us_bct["request_support"]._run(
            support_type="FIRES",
            justification="enemy bunker on east bank",
            priority="HIGH",
        )


def test_request_support_fires_with_coord(all_tools_us_bct):
    out = all_tools_us_bct["request_support"]._run(
        support_type="FIRES",
        justification="enemy bunker on east bank",
        priority="HIGH",
        target_lat_deg=36.18,
        target_lon_deg=-86.78,
        target_alt_m=170.0,
    )
    assert out["validator"] == "skipped"


def test_delegate_subset_check(all_tools_us_bct):
    """Cannot delegate verbs the agent doesn't itself have."""
    with pytest.raises(ToolError) as exc:
        all_tools_us_bct["delegate"]._run(
            to_entity_id=uuid4(),
            delegated_verbs=["jam"],  # us-bct has no 'jam'
            ttl_turns=2,
        )
    assert "cannot delegate verbs not in own authority" in exc.value.reason


def test_delegate_happy(all_tools_us_bct):
    out = all_tools_us_bct["delegate"]._run(
        to_entity_id=uuid4(),
        delegated_verbs=["move_to", "engage"],
        ttl_turns=3,
    )
    assert out["verb"] == "delegate"
    assert out["validator"] == "skipped"


def test_escalate_strictly_higher(all_tools_us_bct):
    """us-bct.commander.echelon=BATTALION; BRIGADE > BATTALION OK."""
    out = all_tools_us_bct["escalate"]._run(
        reason="prep'd to lose comms with BN HQ",
        severity="PRIORITY",
        to_echelon="BRIGADE",
    )
    assert out["verb"] == "escalate"


def test_escalate_sideways_rejected(all_tools_us_bct):
    """BATTALION -> BATTALION must reject; same rank is not strictly higher."""
    with pytest.raises(ToolError) as exc:
        all_tools_us_bct["escalate"]._run(
            reason="trying to bypass override",
            severity="ROUTINE",
            to_echelon="BATTALION",
        )
    assert "not strictly higher" in exc.value.reason


def test_escalate_downward_rejected(all_tools_us_bct):
    """BATTALION -> COMPANY rejects."""
    with pytest.raises(ToolError) as exc:
        all_tools_us_bct["escalate"]._run(
            reason="downward escalate",
            severity="ROUTINE",
            to_echelon="COMPANY",
        )
    assert "not strictly higher" in exc.value.reason
