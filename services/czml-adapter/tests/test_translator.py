"""End-to-end translator tests covering all 7 v1 spatial families.

For each family:
  - Happy path: a properly-shaped event → ACCEPTED with a substituted packet.
  - Reject path: out-of-range params → REJECTED with the validator's reason.

Plus:
  - Verbs without a spatial family → SKIPPED.
  - Validator rejection because the profile lacks the verb (us-bct + jam).
  - Token substitution sanity (whole-value AND interpolated tokens).
"""

from __future__ import annotations

import pytest

from almighty_czml_adapter.models import ResultKind
from almighty_czml_adapter.translator import translate_event

from conftest import make_event


# ---- Happy paths per family --------------------------------------------------


def test_jamming_circle_happy(template_loader, validator, peer_profile, position):
    event = make_event(
        action_verb="jam",
        source_officer_type="COMMUNICATOR",
        payload={
            "target_polygon": [[36.18, -86.78], [36.19, -86.77], [36.17, -86.76]],
            "power_w": 500.0,
            "band": "L",
            "duration_s": 90.0,
            "radius_m": 2_000.0,
        },
    )
    result = translate_event(
        event,
        template_loader=template_loader,
        validator=validator,
        capability_profile=peer_profile,
        entity_position_lookup=lambda _e: position,
    )
    assert result.kind is ResultKind.ACCEPTED
    assert result.family == "jamming_circle"
    # Whole-value token substituted to the actual number.
    assert isinstance(result.packet["ellipse"]["semiMajorAxis"], (int, float))
    assert result.packet["ellipse"]["semiMajorAxis"] == 2_000.0
    # Interpolated token in the description.
    assert "2000" in result.packet["description"] or "2000.0" in result.packet["description"]


def test_indirect_fire_arc_happy(template_loader, validator, us_bct_profile, position):
    event = make_event(
        action_verb="engage",
        source_officer_type="EFFECTOR",
        payload={
            "weapon_system": "notional.indirect.medium",
            "volume_count": 4,
            "intent": "NEUTRALIZE",
            "range_m": 12_000.0,
            "time_of_flight_s": 25.0,
            "dispersion_ellipse_a_m": 80.0,
            "dispersion_ellipse_b_m": 80.0,
            "target_coordinate": {"lat_deg": 36.181, "lon_deg": -86.772, "alt_m": 160.0},
        },
    )
    result = translate_event(
        event,
        template_loader=template_loader,
        validator=validator,
        capability_profile=us_bct_profile,
        entity_position_lookup=lambda _e: position,
    )
    assert result.kind is ResultKind.ACCEPTED
    assert result.family == "indirect_fire_arc"


def test_radar_fan_happy(template_loader, validator, us_bct_profile, position):
    event = make_event(
        action_verb="detect",
        source_officer_type="SENSOR",
        payload={
            "modality": "RADAR",
            "confidence": 0.9,
            "range_m": 10_000.0,
            "azimuth_deg": 90.0,
            "sweep_arc_deg": 60.0,
        },
    )
    result = translate_event(
        event,
        template_loader=template_loader,
        validator=validator,
        capability_profile=us_bct_profile,
        entity_position_lookup=lambda _e: position,
    )
    assert result.kind is ResultKind.ACCEPTED
    assert result.family == "radar_fan"


def test_ew_cone_happy(template_loader, validator, peer_profile, position):
    event = make_event(
        action_verb="detect",
        source_officer_type="SENSOR",
        payload={
            "modality": "RF",
            "confidence": 0.7,
            "range_m": 30_000.0,
            "azimuth_deg": 45.0,
            "beamwidth_deg": 30.0,
            "band": "UHF",
        },
    )
    result = translate_event(
        event,
        template_loader=template_loader,
        validator=validator,
        capability_profile=peer_profile,
        entity_position_lookup=lambda _e: position,
    )
    assert result.kind is ResultKind.ACCEPTED
    assert result.family == "ew_cone"


def test_masint_cell_happy(template_loader, validator, us_bct_profile, position):
    """us-bct profile authorizes masint_cell."""
    event = make_event(
        action_verb="detect",
        source_officer_type="SENSOR",
        payload={
            "modality": "MASINT_MULTI",
            "confidence": 0.6,
            "range_m": 10_000.0,
            "polygon_area_m2": 50_000.0,
            "dwell_s": 600.0,
        },
    )
    result = translate_event(
        event,
        template_loader=template_loader,
        validator=validator,
        capability_profile=us_bct_profile,
        entity_position_lookup=lambda _e: position,
    )
    assert result.kind is ResultKind.ACCEPTED
    assert result.family == "masint_cell"


def test_keyhole_footprint_happy(template_loader, validator, us_bct_profile, position):
    event = make_event(
        action_verb="classify",
        source_officer_type="SENSOR",
        payload={
            "classification_label": "notional.air.uas.medium",
            "confidence": 0.8,
            "dwell_s": 30.0,
            "polygon_area_m2": 25_000.0,
        },
    )
    result = translate_event(
        event,
        template_loader=template_loader,
        validator=validator,
        capability_profile=us_bct_profile,
        entity_position_lookup=lambda _e: position,
    )
    assert result.kind is ResultKind.ACCEPTED
    assert result.family == "keyhole_footprint"


def test_uas_corridor_happy(template_loader, validator, peer_profile, position):
    """peer profile carries uas_corridor in effect_parameter_ranges and
    advertise_corridor=true on its communicator block."""
    event = make_event(
        action_verb="relay",
        source_officer_type="COMMUNICATOR",
        payload={
            "channel": "VHF",
            "is_airborne": True,
            "altitude_band_lower_m": 500.0,
            "altitude_band_upper_m": 2_000.0,
            "width_m": 1_000.0,
        },
    )
    result = translate_event(
        event,
        template_loader=template_loader,
        validator=validator,
        capability_profile=peer_profile,
        entity_position_lookup=lambda _e: position,
    )
    assert result.kind is ResultKind.ACCEPTED
    assert result.family == "uas_corridor"


# ---- Reject paths ------------------------------------------------------------


def test_jamming_circle_out_of_range_rejects(
    template_loader, validator, peer_profile, position
):
    """peer's jamming_circle.power_w max is 1500 W; 5000 must reject."""
    event = make_event(
        action_verb="jam",
        source_officer_type="COMMUNICATOR",
        payload={
            "target_polygon": [[36.18, -86.78], [36.19, -86.77], [36.17, -86.76]],
            "power_w": 5_000.0,  # over peer cap
            "band": "L",
            "duration_s": 60.0,
            "radius_m": 2_000.0,
        },
    )
    result = translate_event(
        event,
        template_loader=template_loader,
        validator=validator,
        capability_profile=peer_profile,
        entity_position_lookup=lambda _e: position,
    )
    assert result.kind is ResultKind.REJECTED
    assert result.family == "jamming_circle"
    assert "power_w" in result.reason


def test_us_bct_jam_event_rejects_at_verb_gate(
    template_loader, validator, us_bct_profile, position
):
    """us-bct profile lacks the `jam` verb, so the validator rejects at
    the verb-emission gate before reaching range checks. Capability
    gating verified — DoD requirement."""
    event = make_event(
        action_verb="jam",
        source_officer_type="COMMUNICATOR",
        payload={
            "target_polygon": [[36.18, -86.78], [36.19, -86.77], [36.17, -86.76]],
            "power_w": 100.0,  # in-range
            "band": "VHF",
            "duration_s": 30.0,
            "radius_m": 1_000.0,
        },
    )
    result = translate_event(
        event,
        template_loader=template_loader,
        validator=validator,
        capability_profile=us_bct_profile,
        entity_position_lookup=lambda _e: position,
    )
    assert result.kind is ResultKind.REJECTED
    assert result.family == "jamming_circle"
    assert "jam" in result.reason  # validator's verb-gate reason


def test_engage_out_of_range_rejects(
    template_loader, validator, us_bct_profile, position
):
    """us-bct indirect_fire_arc.range_m max is 25000; 50000 must reject."""
    event = make_event(
        action_verb="engage",
        source_officer_type="EFFECTOR",
        payload={
            "weapon_system": "notional.indirect.medium",
            "volume_count": 1,
            "range_m": 50_000.0,  # over cap
            "time_of_flight_s": 30.0,
            "dispersion_ellipse_a_m": 50.0,
            "dispersion_ellipse_b_m": 50.0,
        },
    )
    result = translate_event(
        event,
        template_loader=template_loader,
        validator=validator,
        capability_profile=us_bct_profile,
        entity_position_lookup=lambda _e: position,
    )
    assert result.kind is ResultKind.REJECTED
    assert "range_m" in result.reason


# ---- Skip paths --------------------------------------------------------------


@pytest.mark.parametrize(
    "verb,officer",
    [
        ("move_to", "MOVER"),
        ("halt", "MOVER"),
        ("assume_posture", "MOVER"),
        ("send", "COMMUNICATOR"),
        ("report", "COMMUNICATOR"),
        ("issue_order", "COMMANDER"),
        ("escalate", "COMMANDER"),
        ("delegate", "COMMANDER"),
    ],
)
def test_non_spatial_verb_skipped(
    verb, officer, template_loader, validator, us_bct_profile, position
):
    event = make_event(action_verb=verb, source_officer_type=officer)
    result = translate_event(
        event,
        template_loader=template_loader,
        validator=validator,
        capability_profile=us_bct_profile,
        entity_position_lookup=lambda _e: position,
    )
    assert result.kind is ResultKind.SKIPPED
    assert result.packet is None
    assert result.family is None


def test_eo_ir_detect_skipped(
    template_loader, validator, us_bct_profile, position
):
    """EO_IR has no spatial CZML template in v1 (per WS-108 § 6.1).
    The translator skips rather than failing."""
    event = make_event(
        action_verb="detect",
        source_officer_type="SENSOR",
        payload={"modality": "EO_IR", "confidence": 0.7, "range_m": 4_000.0},
    )
    result = translate_event(
        event,
        template_loader=template_loader,
        validator=validator,
        capability_profile=us_bct_profile,
        entity_position_lookup=lambda _e: position,
    )
    assert result.kind is ResultKind.SKIPPED


# ---- Token substitution sanity ----------------------------------------------


def test_packet_carries_artifact_id_and_owning_entity(
    template_loader, validator, us_bct_profile, position
):
    event = make_event(
        action_verb="engage",
        source_officer_type="EFFECTOR",
        payload={
            "weapon_system": "notional.indirect.medium",
            "volume_count": 1,
            "range_m": 5_000.0,
            "time_of_flight_s": 15.0,
            "dispersion_ellipse_a_m": 50.0,
            "dispersion_ellipse_b_m": 50.0,
        },
    )
    result = translate_event(
        event,
        template_loader=template_loader,
        validator=validator,
        capability_profile=us_bct_profile,
        entity_position_lookup=lambda _e: position,
    )
    assert result.kind is ResultKind.ACCEPTED
    # Whole-value token: packet.id is the synthesized artifact_id, NOT
    # the literal "{{artifact_id}}" string.
    assert "{{" not in result.packet["id"]
    # Interpolated: owning_entity_id substituted into name / description.
    assert str(event.source_entity_id) in result.packet.get("name", "")


def test_validator_params_subset_carried_on_result(
    template_loader, validator, us_bct_profile, position
):
    """validator_params on an ACCEPTED result should reflect what was
    passed to the validator — useful for debug + AAR audit."""
    event = make_event(
        action_verb="engage",
        source_officer_type="EFFECTOR",
        payload={
            "weapon_system": "notional.indirect.medium",
            "volume_count": 1,
            "range_m": 5_000.0,
            "time_of_flight_s": 15.0,
            "dispersion_ellipse_a_m": 50.0,
            "dispersion_ellipse_b_m": 50.0,
        },
    )
    result = translate_event(
        event,
        template_loader=template_loader,
        validator=validator,
        capability_profile=us_bct_profile,
        entity_position_lookup=lambda _e: position,
    )
    assert result.validator_params["range_m"] == 5_000.0
    assert result.validator_params["time_of_flight_s"] == 15.0
