"""Tests for the four Sensor verbs."""

from __future__ import annotations

from uuid import uuid4

import pytest

from almighty_officer_tools import ToolError


def test_detect_radar_happy(all_tools_us_bct):
    """detect with modality=RADAR -> radar_fan validator path; us-bct has both."""
    out = all_tools_us_bct["detect"]._run(
        target_entity_id=uuid4(),
        modality="RADAR",
        confidence=0.9,
        range_m=10_000.0,
    )
    assert out["verb"] == "detect"
    assert out["officer_type"] == "SENSOR"
    assert out["validator"] == "accepted"


def test_detect_eo_ir_no_validator(all_tools_us_bct):
    """detect with modality=EO_IR -> no spatial artifact -> validator skipped."""
    out = all_tools_us_bct["detect"]._run(
        target_entity_id=uuid4(),
        modality="EO_IR",
        confidence=0.7,
        range_m=2_000.0,
    )
    assert out["validator"] == "skipped"


def test_detect_radar_out_of_range_rejects(all_tools_us_bct, us_bct_profile):
    """range_m exceeding intersect(template, profile) -> validator reject."""
    # us-bct radar_fan profile.range_m max is 50000; template max is 80000;
    # intersect = 50000. 100000 should reject.
    with pytest.raises(ToolError) as exc:
        all_tools_us_bct["detect"]._run(
            target_entity_id=uuid4(),
            modality="RADAR",
            confidence=0.9,
            range_m=100_000.0,
        )
    assert "validator rejected 'detect'" in exc.value.reason
    assert "range_m" in exc.value.reason


def test_track_no_validator(all_tools_us_bct):
    out = all_tools_us_bct["track"]._run(
        target_entity_id=uuid4(),
        update_rate_hz=2.0,
    )
    assert out["verb"] == "track"
    assert out["validator"] == "skipped"


def test_classify_uses_keyhole_footprint(all_tools_us_bct):
    out = all_tools_us_bct["classify"]._run(
        track_id=uuid4(),
        classification_label="notional.air.uas.medium",
        confidence=0.8,
        dwell_s=30.0,
    )
    assert out["verb"] == "classify"
    assert out["validator"] == "accepted"


def test_lose_track_no_validator(all_tools_us_bct):
    out = all_tools_us_bct["lose_track"]._run(
        track_id=uuid4(),
        reason="OUT_OF_RANGE",
    )
    assert out["validator"] == "skipped"
