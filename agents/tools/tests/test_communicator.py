"""Tests for the four Communicator verbs."""

from __future__ import annotations

from uuid import uuid4

import pytest

from almighty_officer_tools import ToolError


def test_send_no_validator(all_tools_us_bct):
    out = all_tools_us_bct["send"]._run(
        channel="VHF",
        message_payload={"line": "test"},
        recipient_role="BATTALION_S3",
    )
    assert out["verb"] == "send"
    assert out["validator"] == "skipped"


def test_relay_non_airborne_no_corridor(all_tools_us_bct):
    """us-bct has advertise_corridor=false. Even if relay is_airborne=True,
    no uas_corridor validator path fires."""
    out = all_tools_us_bct["relay"]._run(
        source_entity_id=uuid4(),
        recipient_entity_id=uuid4(),
        channel="VHF",
        is_airborne=True,
    )
    assert out["validator"] == "skipped"


def test_relay_airborne_with_corridor(all_tools_peer):
    """peer.json has advertise_corridor=true AND uas_corridor in
    effect_parameter_ranges + 'relay' in action_verbs_available."""
    out = all_tools_peer["relay"]._run(
        source_entity_id=uuid4(),
        recipient_entity_id=uuid4(),
        channel="VHF",
        is_airborne=True,
    )
    assert out["validator"] == "accepted"


def test_jam_happy_on_peer(all_tools_peer):
    """peer.json has 'jam' verb + jamming_circle ranges + L band."""
    out = all_tools_peer["jam"]._run(
        target_polygon=[[36.18, -86.78], [36.19, -86.77], [36.17, -86.76]],
        power_w=500.0,
        band="L",
        duration_s=120.0,
        radius_m=2_000.0,
    )
    assert out["validator"] == "accepted"


def test_jam_out_of_range_rejects(all_tools_peer):
    """peer jamming_circle.power_w max is 1500; 5000 must reject."""
    with pytest.raises(ToolError) as exc:
        all_tools_peer["jam"]._run(
            target_polygon=[[36.18, -86.78], [36.19, -86.77], [36.17, -86.76]],
            power_w=5_000.0,
            band="L",
            duration_s=60.0,
            radius_m=2_000.0,
        )
    assert "validator rejected 'jam'" in exc.value.reason
    assert "power_w" in exc.value.reason


def test_report_no_validator(all_tools_us_bct):
    out = all_tools_us_bct["report"]._run(
        report_type="SITREP",
        report_payload={"line1": "no contact"},
        to_echelon="BRIGADE",
    )
    assert out["validator"] == "skipped"
