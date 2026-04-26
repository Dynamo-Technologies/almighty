"""Communicator.jam — deny use of an RF band over an area.

Per WS-105 + WS-108: omni jammers emit `jamming_circle`. Directional
jammers can emit `ew_cone`; for v1 the tool always uses jamming_circle.
WS-202 / WS-201's directional-vs-omni dispatch is a future refinement.
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, model_validator

from ..base import OfficerToolBase

RfBand = Literal["HF", "VHF", "UHF", "L", "S", "C", "X", "KU", "KA"]


class JamArgs(BaseModel):
    target_polygon: list[list[float]]
    power_w: float = Field(gt=0)
    band: RfBand
    duration_s: float = Field(gt=0)
    # Validator-side circle approximation; v1 keeps it simple.
    radius_m: float = Field(gt=0, default=2_000.0)

    @model_validator(mode="after")
    def _polygon_shape(self) -> "JamArgs":
        if len(self.target_polygon) < 3:
            raise ValueError("jam.target_polygon must have ≥ 3 vertices")
        return self


class JamTool(OfficerToolBase):
    OFFICER_TYPE: ClassVar[str] = "COMMUNICATOR"
    VERB: ClassVar[str] = "jam"
    EFFECT_FAMILY: ClassVar[str | None] = "jamming_circle"

    name: str = "almighty.communicator.jam"
    description: str = "Deny use of an RF band over an area."
    args_schema: type[BaseModel] = JamArgs

    def _build_validator_params(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, JamArgs)
        return {"radius_m": args.radius_m, "power_w": args.power_w}

    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, JamArgs)
        return {
            "target_polygon": args.target_polygon,
            "power_w": args.power_w,
            "band": args.band,
            "duration_s": args.duration_s,
            "radius_m": args.radius_m,
        }
