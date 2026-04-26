"""Per-family translators.

Each family has:

  detector(event)        -> bool : does this event produce this family?
  token_builder(event,
                position,
                artifact_id) -> dict : full token map for the template
                                       substitution + validator params.
  validator_param_keys   : list[str] : subset of tokens passed to the
                                       validator's `params` dict.

The translator iterates families in priority order (per WS-108 § 6
emission rules) and dispatches on the first match. Caller-supplied
``entity_position_lookup`` provides emitter-anchored coordinates for
shapes that need them (jamming circle origin, EW cone apex, etc.).

v1 family coverage (7 of 9):

  jamming_circle, indirect_fire_arc, radar_fan, ew_cone, masint_cell,
  keyhole_footprint, uas_corridor

Deferred to v2:

  - ir_plume     — needs kernel-side follow-on event emission from
                   `Effector.destroy` (no machinery yet).
  - satellite_swath — needs SPACE_UNIT entity-type signal that the
                   adapter doesn't currently get from events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from uuid import UUID, uuid4

from almighty_kernel.dag import KernelEvent

from .models import EntityPosition

TokenBuilder = Callable[[KernelEvent, EntityPosition, UUID], dict[str, Any]]


@dataclass(frozen=True)
class FamilyHandler:
    family: str  # underscored: jamming_circle
    template_id: str  # hyphenated: jamming-circle
    detector: Callable[[KernelEvent], bool]
    token_builder: TokenBuilder
    validator_param_keys: tuple[str, ...]


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------


def _detect_jamming_circle(e: KernelEvent) -> bool:
    if e.action_verb == "jam":
        return True
    if e.action_verb == "disable" and e.payload.get("method") == "EW":
        return True
    return False


def _detect_indirect_fire_arc(e: KernelEvent) -> bool:
    if e.action_verb in ("engage", "suppress", "destroy"):
        return True
    if e.action_verb == "disable" and e.payload.get("method") == "KINETIC":
        return True
    return False


def _detect_radar_fan(e: KernelEvent) -> bool:
    return (
        e.action_verb in ("detect", "track")
        and e.payload.get("modality") == "RADAR"
    )


def _detect_ew_cone(e: KernelEvent) -> bool:
    return e.action_verb == "detect" and e.payload.get("modality") == "RF"


def _detect_masint_cell(e: KernelEvent) -> bool:
    if e.action_verb in ("detect", "classify") and e.payload.get("modality") in (
        "ACOUSTIC",
        "SEISMIC",
        "MASINT_MULTI",
    ):
        return True
    return False


def _detect_keyhole_footprint(e: KernelEvent) -> bool:
    return e.action_verb == "classify" and e.payload.get("modality") not in (
        "ACOUSTIC",
        "SEISMIC",
        "MASINT_MULTI",
    )


def _detect_uas_corridor(e: KernelEvent) -> bool:
    return (
        e.action_verb == "relay"
        and bool(e.payload.get("is_airborne"))
        # advertise_corridor is a profile flag the WS-402 RelayTool
        # already enforced — by the time we see the event, presence of
        # is_airborne=True is the signal.
    )


# ---------------------------------------------------------------------------
# Token builders
#
# Common tokens (id, name, time validity) are stamped by every builder.
# Per-family tokens come straight from the event payload.
# ---------------------------------------------------------------------------


def _common_tokens(
    event: KernelEvent,
    artifact_id: UUID,
    *,
    duration_s: float = 60.0,
) -> dict[str, Any]:
    return {
        "artifact_id": str(artifact_id),
        "owning_entity_id": str(event.source_entity_id),
        "time_validity_start": event.ts.isoformat(),
        "time_validity_end": _shift_iso(event.ts.isoformat(), duration_s),
    }


def _shift_iso(iso: str, seconds: float) -> str:
    """Shift an ISO-8601 timestamp by N seconds. Naive — uses datetime
    parser; v1 duration math is per-event-per-family."""
    from datetime import datetime, timedelta, timezone

    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt + timedelta(seconds=seconds)).isoformat()


# Default colors per family (CZML rgba). Templates also have defaults;
# we substitute matching ones so the packet is fully determined.
_RED_FILL = [255, 80, 60, 90]
_RED_OUTLINE = [255, 80, 60, 220]
_BLUE_FILL = [60, 140, 255, 90]
_BLUE_OUTLINE = [60, 140, 255, 220]
_AMBER_FILL = [255, 200, 60, 90]
_AMBER_OUTLINE = [255, 200, 60, 220]


def _build_jamming_circle(
    event: KernelEvent, position: EntityPosition, artifact_id: UUID
) -> dict[str, Any]:
    payload = event.payload
    duration = float(payload.get("duration_s", 60.0))
    return {
        **_common_tokens(event, artifact_id, duration_s=duration),
        "origin_lat_deg": position.lat_deg,
        "origin_lon_deg": position.lon_deg,
        "origin_alt_m": position.alt_m,
        "radius_m": float(payload["radius_m"]),
        "power_w": float(payload["power_w"]),
        "band": str(payload.get("band", "VHF")),
        "fill_rgba": _RED_FILL,
        "outline_rgba": _RED_OUTLINE,
    }


def _build_indirect_fire_arc(
    event: KernelEvent, position: EntityPosition, artifact_id: UUID
) -> dict[str, Any]:
    payload = event.payload
    target = payload.get("target_coordinate") or {}
    impact_lat = float(target.get("lat_deg", position.lat_deg))
    impact_lon = float(target.get("lon_deg", position.lon_deg))
    impact_alt = float(target.get("alt_m", position.alt_m))
    tof = float(payload.get("time_of_flight_s", 0.0))
    return {
        **_common_tokens(event, artifact_id, duration_s=tof + 30.0),
        "firing_lat_deg": position.lat_deg,
        "firing_lon_deg": position.lon_deg,
        "firing_alt_m": position.alt_m,
        "impact_lat_deg": impact_lat,
        "impact_lon_deg": impact_lon,
        "impact_alt_m": impact_alt,
        "range_m": float(payload["range_m"]),
        "time_of_flight_s": tof,
        "dispersion_ellipse_a_m": float(payload.get("dispersion_ellipse_a_m", 50.0)),
        "dispersion_ellipse_b_m": float(payload.get("dispersion_ellipse_b_m", 50.0)),
        "mode": event.action_verb,  # engage / suppress / destroy / disable
        "volume_count": int(payload.get("volume_count", 1)),
        "fill_rgba": _RED_FILL,
        "outline_rgba": _RED_OUTLINE,
    }


def _build_radar_fan(
    event: KernelEvent, position: EntityPosition, artifact_id: UUID
) -> dict[str, Any]:
    payload = event.payload
    return {
        **_common_tokens(event, artifact_id, duration_s=120.0),
        "origin_lat_deg": position.lat_deg,
        "origin_lon_deg": position.lon_deg,
        "origin_alt_m": position.alt_m,
        "azimuth_deg": float(payload.get("azimuth_deg", 0.0)),
        "sweep_arc_deg": float(payload.get("sweep_arc_deg", 60.0)),
        "range_m": float(payload["range_m"]),
        "elevation_deg": float(payload.get("elevation_deg", 0.0)),
        "fill_rgba": _BLUE_FILL,
        "outline_rgba": _BLUE_OUTLINE,
    }


def _build_ew_cone(
    event: KernelEvent, position: EntityPosition, artifact_id: UUID
) -> dict[str, Any]:
    payload = event.payload
    return {
        **_common_tokens(event, artifact_id, duration_s=60.0),
        "origin_lat_deg": position.lat_deg,
        "origin_lon_deg": position.lon_deg,
        "origin_alt_m": position.alt_m,
        "azimuth_deg": float(payload.get("azimuth_deg", 0.0)),
        "beamwidth_deg": float(payload.get("beamwidth_deg", 30.0)),
        "effective_range_m": float(payload["range_m"]),
        "band": str(payload.get("band", "RF")),
        "fill_rgba": _BLUE_FILL,
        "outline_rgba": _BLUE_OUTLINE,
    }


def _build_masint_cell(
    event: KernelEvent, position: EntityPosition, artifact_id: UUID
) -> dict[str, Any]:
    payload = event.payload
    polygon_area = float(payload.get("polygon_area_m2", 50_000.0))
    return {
        **_common_tokens(event, artifact_id, duration_s=600.0),
        "origin_lat_deg": position.lat_deg,
        "origin_lon_deg": position.lon_deg,
        "origin_alt_m": position.alt_m,
        "polygon_area_m2": polygon_area,
        "dwell_s": float(payload.get("dwell_s", 600.0)),
        "fill_rgba": _AMBER_FILL,
        "outline_rgba": _AMBER_OUTLINE,
    }


def _build_keyhole_footprint(
    event: KernelEvent, position: EntityPosition, artifact_id: UUID
) -> dict[str, Any]:
    payload = event.payload
    polygon_area = float(payload.get("polygon_area_m2", 25_000.0))
    return {
        **_common_tokens(event, artifact_id, duration_s=300.0),
        "origin_lat_deg": position.lat_deg,
        "origin_lon_deg": position.lon_deg,
        "origin_alt_m": position.alt_m,
        "polygon_area_m2": polygon_area,
        "fill_rgba": _BLUE_FILL,
        "outline_rgba": _BLUE_OUTLINE,
    }


def _build_uas_corridor(
    event: KernelEvent, position: EntityPosition, artifact_id: UUID
) -> dict[str, Any]:
    payload = event.payload
    return {
        **_common_tokens(event, artifact_id, duration_s=300.0),
        "origin_lat_deg": position.lat_deg,
        "origin_lon_deg": position.lon_deg,
        "origin_alt_m": position.alt_m,
        "altitude_band_lower_m": float(payload.get("altitude_band_lower_m", 500.0)),
        "altitude_band_upper_m": float(payload.get("altitude_band_upper_m", 2_000.0)),
        "width_m": float(payload.get("width_m", 2_000.0)),
        "fill_rgba": _BLUE_FILL,
        "outline_rgba": _BLUE_OUTLINE,
    }


# ---------------------------------------------------------------------------
# Registry — order matters when verbs map to multiple families (uncommon).
# ---------------------------------------------------------------------------

_HANDLERS: tuple[FamilyHandler, ...] = (
    FamilyHandler(
        family="jamming_circle",
        template_id="jamming-circle",
        detector=_detect_jamming_circle,
        token_builder=_build_jamming_circle,
        validator_param_keys=("radius_m", "power_w"),
    ),
    FamilyHandler(
        family="indirect_fire_arc",
        template_id="indirect-fire-arc",
        detector=_detect_indirect_fire_arc,
        token_builder=_build_indirect_fire_arc,
        validator_param_keys=(
            "range_m",
            "time_of_flight_s",
            "dispersion_ellipse_a_m",
            "dispersion_ellipse_b_m",
        ),
    ),
    FamilyHandler(
        family="radar_fan",
        template_id="radar-fan",
        detector=_detect_radar_fan,
        token_builder=_build_radar_fan,
        validator_param_keys=("azimuth_deg", "sweep_arc_deg", "range_m"),
    ),
    FamilyHandler(
        family="ew_cone",
        template_id="ew-cone",
        detector=_detect_ew_cone,
        token_builder=_build_ew_cone,
        validator_param_keys=("azimuth_deg", "beamwidth_deg", "effective_range_m"),
    ),
    FamilyHandler(
        family="masint_cell",
        template_id="masint-cell",
        detector=_detect_masint_cell,
        token_builder=_build_masint_cell,
        validator_param_keys=("polygon_area_m2", "dwell_s"),
    ),
    FamilyHandler(
        family="keyhole_footprint",
        template_id="keyhole-footprint",
        detector=_detect_keyhole_footprint,
        token_builder=_build_keyhole_footprint,
        validator_param_keys=("polygon_area_m2",),
    ),
    FamilyHandler(
        family="uas_corridor",
        template_id="uas-corridor",
        detector=_detect_uas_corridor,
        token_builder=_build_uas_corridor,
        validator_param_keys=("altitude_band_lower_m", "altitude_band_upper_m", "width_m"),
    ),
)


def find_handler(event: KernelEvent) -> FamilyHandler | None:
    """Return the first matching family handler, or None if no spatial
    family applies to this event (e.g., Mover verbs, Commander verbs,
    Communicator non-spatial verbs)."""
    for handler in _HANDLERS:
        if handler.detector(event):
            return handler
    return None


def new_artifact_id() -> UUID:
    return uuid4()
