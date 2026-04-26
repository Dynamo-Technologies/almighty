"""Mover.follow_route — move along a sequence of waypoints."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, Field, model_validator

from ..base import OfficerToolBase


class Waypoint(BaseModel):
    lat_deg: float = Field(ge=-90, le=90)
    lon_deg: float = Field(ge=-180, le=180)
    alt_m: float


class FollowRouteArgs(BaseModel):
    waypoints: list[Waypoint]
    speed_mps: float | None = Field(default=None, gt=0)
    loop: bool = False

    @model_validator(mode="after")
    def _non_empty(self) -> "FollowRouteArgs":
        if not self.waypoints:
            raise ValueError("follow_route requires waypoints length >= 1")
        return self


class FollowRouteTool(OfficerToolBase):
    OFFICER_TYPE: ClassVar[str] = "MOVER"
    VERB: ClassVar[str] = "follow_route"
    EFFECT_FAMILY: ClassVar[str | None] = None

    name: str = "almighty.mover.follow_route"
    description: str = "Move along a sequence of waypoints."
    args_schema: type[BaseModel] = FollowRouteArgs

    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, FollowRouteArgs)
        return {
            "waypoints": [w.model_dump() for w in args.waypoints],
            "speed_mps": args.speed_mps,
            "loop": args.loop,
        }
