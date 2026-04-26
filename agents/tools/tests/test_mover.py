"""Tests for the four Mover verbs. None call the validator (no spatial artifacts)."""

from __future__ import annotations


def test_move_to(all_tools_us_bct):
    out = all_tools_us_bct["move_to"]._run(
        target_lat_deg=36.20,
        target_lon_deg=-86.78,
        target_alt_m=170.0,
    )
    assert out["verb"] == "move_to"
    assert out["validator"] == "skipped"


def test_follow_route(all_tools_us_bct):
    out = all_tools_us_bct["follow_route"]._run(
        waypoints=[
            {"lat_deg": 36.18, "lon_deg": -86.78, "alt_m": 165.0},
            {"lat_deg": 36.19, "lon_deg": -86.77, "alt_m": 167.0},
        ],
        speed_mps=10.0,
    )
    assert out["verb"] == "follow_route"
    assert out["validator"] == "skipped"


def test_halt_no_args(all_tools_us_bct):
    out = all_tools_us_bct["halt"]._run()
    assert out["verb"] == "halt"
    assert out["validator"] == "skipped"


def test_assume_posture(all_tools_us_bct):
    out = all_tools_us_bct["assume_posture"]._run(posture="DUG_IN")
    assert out["verb"] == "assume_posture"
    assert out["validator"] == "skipped"
