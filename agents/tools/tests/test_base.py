"""Tests for the base flow: capability gate fires before validator,
unknown verb raises ToolError without touching the validator, etc."""

from __future__ import annotations

import pytest

from almighty_officer_tools import ToolError, build_all_tools

from almighty_officer_tools.registry import ALL_TOOL_CLASSES


def test_all_twenty_tools_built(us_bct_profile, context_factory):
    tools = build_all_tools(context_factory(us_bct_profile))
    assert len(tools) == 20
    # Verb names match WS-105 lock list.
    expected = {
        "detect", "track", "classify", "lose_track",
        "engage", "suppress", "destroy", "disable",
        "move_to", "follow_route", "halt", "assume_posture",
        "send", "relay", "jam", "report",
        "issue_order", "request_support", "delegate", "escalate",
    }
    assert set(tools.keys()) == expected


def test_capability_gate_blocks_missing_verb(context_factory, us_bct_profile):
    """us-bct.json has no 'jam' verb -> JamTool must reject before
    touching the validator. Confirms the gate fires."""
    assert "jam" not in us_bct_profile["action_verbs_available"]
    tools = build_all_tools(context_factory(us_bct_profile))
    with pytest.raises(ToolError) as exc:
        tools["jam"]._run(
            target_polygon=[[36.18, -86.78], [36.19, -86.77], [36.17, -86.76]],
            power_w=100.0,
            band="VHF",
            duration_s=60.0,
        )
    assert "capability gate" in exc.value.reason
    assert "'jam'" in exc.value.reason


def test_tool_classes_unique_verbs():
    """Sanity: no two tool classes share a VERB."""
    verbs = [c.VERB for c in ALL_TOOL_CLASSES]
    assert len(verbs) == len(set(verbs)), "duplicate VERB found among tool classes"


def test_all_tools_subclass_basetool():
    """Sanity: all tool classes inherit crewai.tools.BaseTool indirectly."""
    from crewai.tools import BaseTool

    for cls in ALL_TOOL_CLASSES:
        assert issubclass(cls, BaseTool), f"{cls.__name__} must subclass crewai BaseTool"
