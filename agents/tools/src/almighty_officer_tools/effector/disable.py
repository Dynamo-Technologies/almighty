"""Effector.disable — render a target non-functional, method-dependent.

Per WS-105:
  KINETIC -> indirect_fire_arc artifact, target enters 'disabled'.
  EW      -> jamming_circle artifact (borrows Communicator.jam capability).
  CYBER   -> non-spatial; no artifact, no validator call.
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from ..base import OfficerToolBase

DisableMethod = Literal["KINETIC", "EW", "CYBER"]

_FAMILY_BY_METHOD: dict[DisableMethod, str | None] = {
    "KINETIC": "indirect_fire_arc",
    "EW": "jamming_circle",
    "CYBER": None,
}


class DisableArgs(BaseModel):
    target_entity_id: UUID
    method: DisableMethod
    weapon_system: str = Field(min_length=1)
    intensity: float | None = Field(default=None, ge=0)
    # Validator params per method; defaults are reasonable midpoints. Real
    # callers (WS-403/404) should supply method-appropriate values.
    range_m: float = Field(gt=0, default=10_000.0)
    time_of_flight_s: float = Field(ge=0, default=10.0)
    dispersion_ellipse_a_m: float = Field(gt=0, default=50.0)
    dispersion_ellipse_b_m: float = Field(gt=0, default=50.0)
    radius_m: float = Field(gt=0, default=2_000.0)
    power_w: float = Field(gt=0, default=200.0)


class DisableTool(OfficerToolBase):
    OFFICER_TYPE: ClassVar[str] = "EFFECTOR"
    VERB: ClassVar[str] = "disable"
    EFFECT_FAMILY: ClassVar[str | None] = None  # method-dependent

    name: str = "almighty.effector.disable"
    description: str = "Render a target non-functional via KINETIC, EW, or CYBER method."
    args_schema: type[BaseModel] = DisableArgs

    def _effect_family_for(self, args: BaseModel) -> str | None:
        assert isinstance(args, DisableArgs)
        return _FAMILY_BY_METHOD[args.method]

    def _build_validator_params(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, DisableArgs)
        family = _FAMILY_BY_METHOD[args.method]
        if family == "indirect_fire_arc":
            return {
                "range_m": args.range_m,
                "time_of_flight_s": args.time_of_flight_s,
                "dispersion_ellipse_a_m": args.dispersion_ellipse_a_m,
                "dispersion_ellipse_b_m": args.dispersion_ellipse_b_m,
            }
        if family == "jamming_circle":
            return {"radius_m": args.radius_m, "power_w": args.power_w}
        # CYBER -> no validator call.
        raise AssertionError(f"unreachable: family={family}")

    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, DisableArgs)
        return {
            "target_entity_id": str(args.target_entity_id),
            "method": args.method,
            "weapon_system": args.weapon_system,
            "intensity": args.intensity,
        }
