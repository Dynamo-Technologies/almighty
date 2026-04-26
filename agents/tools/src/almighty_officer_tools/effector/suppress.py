"""Effector.suppress — apply effect to deny use of an area or asset."""

from __future__ import annotations

from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ..base import OfficerToolBase


class SuppressArgs(BaseModel):
    weapon_system: str = Field(min_length=1)
    duration_s: float = Field(gt=0)
    rate_per_min: float = Field(gt=0)
    target_lat_deg: float = Field(ge=-90, le=90)
    target_lon_deg: float = Field(ge=-180, le=180)
    target_alt_m: float = 0.0
    target_polygon: list[list[float]] | None = None
    range_m: float = Field(gt=0)
    time_of_flight_s: float = Field(ge=0)
    dispersion_ellipse_a_m: float = Field(gt=0, default=80.0)
    dispersion_ellipse_b_m: float = Field(gt=0, default=80.0)

    @model_validator(mode="after")
    def _polygon_shape(self) -> "SuppressArgs":
        if self.target_polygon is not None and len(self.target_polygon) < 3:
            raise ValueError("target_polygon, when set, must have ≥ 3 vertices")
        return self


class SuppressTool(OfficerToolBase):
    OFFICER_TYPE: ClassVar[str] = "EFFECTOR"
    VERB: ClassVar[str] = "suppress"
    EFFECT_FAMILY: ClassVar[str | None] = "indirect_fire_arc"

    name: str = "almighty.effector.suppress"
    description: str = "Apply effect to deny use of an area without destroying it."
    args_schema: type[BaseModel] = SuppressArgs

    def _build_validator_params(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, SuppressArgs)
        return {
            "range_m": args.range_m,
            "time_of_flight_s": args.time_of_flight_s,
            "dispersion_ellipse_a_m": args.dispersion_ellipse_a_m,
            "dispersion_ellipse_b_m": args.dispersion_ellipse_b_m,
        }

    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, SuppressArgs)
        return {
            "weapon_system": args.weapon_system,
            "mode": "suppression",
            "duration_s": args.duration_s,
            "rate_per_min": args.rate_per_min,
            "target_coordinate": {
                "lat_deg": args.target_lat_deg,
                "lon_deg": args.target_lon_deg,
                "alt_m": args.target_alt_m,
            },
            "target_polygon": args.target_polygon,
            "range_m": args.range_m,
            "time_of_flight_s": args.time_of_flight_s,
        }
