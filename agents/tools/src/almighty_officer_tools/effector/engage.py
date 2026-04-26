"""Effector.engage — apply effect to a target.

For v1, all effector tools route to the `indirect_fire_arc` family for
the validator gate (templates for direct-fire are out of WS-201 scope).
The verb-distinguishing data lives on the kernel event payload.
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ..base import OfficerToolBase

EngageIntent = Literal["NEUTRALIZE", "SUPPRESS_AND_HOLD", "MARKER"]


class EngageArgs(BaseModel):
    weapon_system: str = Field(min_length=1)
    volume_count: int = Field(ge=1)
    target_entity_id: UUID | None = None
    target_lat_deg: float | None = Field(default=None, ge=-90, le=90)
    target_lon_deg: float | None = Field(default=None, ge=-180, le=180)
    target_alt_m: float | None = None
    intent: EngageIntent = "NEUTRALIZE"
    range_m: float = Field(gt=0)
    time_of_flight_s: float = Field(ge=0)
    dispersion_ellipse_a_m: float = Field(gt=0, default=50.0)
    dispersion_ellipse_b_m: float = Field(gt=0, default=50.0)

    @model_validator(mode="after")
    def _target_xor(self) -> "EngageArgs":
        has_entity = self.target_entity_id is not None
        has_coord = (
            self.target_lat_deg is not None
            and self.target_lon_deg is not None
            and self.target_alt_m is not None
        )
        if has_entity == has_coord:
            raise ValueError(
                "engage requires exactly one of target_entity_id or "
                "(target_lat_deg, target_lon_deg, target_alt_m)"
            )
        return self


class EngageTool(OfficerToolBase):
    OFFICER_TYPE: ClassVar[str] = "EFFECTOR"
    VERB: ClassVar[str] = "engage"
    EFFECT_FAMILY: ClassVar[str | None] = "indirect_fire_arc"

    name: str = "almighty.effector.engage"
    description: str = "Apply effect to a target."
    args_schema: type[BaseModel] = EngageArgs

    def _build_validator_params(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, EngageArgs)
        return {
            "range_m": args.range_m,
            "time_of_flight_s": args.time_of_flight_s,
            "dispersion_ellipse_a_m": args.dispersion_ellipse_a_m,
            "dispersion_ellipse_b_m": args.dispersion_ellipse_b_m,
        }

    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, EngageArgs)
        return {
            "weapon_system": args.weapon_system,
            "volume_count": args.volume_count,
            "target_entity_id": str(args.target_entity_id) if args.target_entity_id else None,
            "target_coordinate": (
                {
                    "lat_deg": args.target_lat_deg,
                    "lon_deg": args.target_lon_deg,
                    "alt_m": args.target_alt_m,
                }
                if args.target_entity_id is None
                else None
            ),
            "intent": args.intent,
            "range_m": args.range_m,
            "time_of_flight_s": args.time_of_flight_s,
        }
