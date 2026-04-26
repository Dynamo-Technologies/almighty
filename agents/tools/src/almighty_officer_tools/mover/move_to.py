"""Mover.move_to — move to a single coordinate.

Per WS-105 and the better-late-than-never doc: Mover verbs emit no
spatial artifacts. No validator call.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, Field

from ..base import OfficerToolBase


class MoveToArgs(BaseModel):
    target_lat_deg: float = Field(ge=-90, le=90)
    target_lon_deg: float = Field(ge=-180, le=180)
    target_alt_m: float
    speed_mps: float | None = Field(default=None, gt=0)


class MoveToTool(OfficerToolBase):
    OFFICER_TYPE: ClassVar[str] = "MOVER"
    VERB: ClassVar[str] = "move_to"
    EFFECT_FAMILY: ClassVar[str | None] = None

    name: str = "almighty.mover.move_to"
    description: str = "Move to a single coordinate."
    args_schema: type[BaseModel] = MoveToArgs

    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, MoveToArgs)
        return {
            "target_lat_deg": args.target_lat_deg,
            "target_lon_deg": args.target_lon_deg,
            "target_alt_m": args.target_alt_m,
            "speed_mps": args.speed_mps,
        }
