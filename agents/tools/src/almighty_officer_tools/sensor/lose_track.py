"""Sensor.lose_track — close an open track.

Per WS-105: no spatial artifact; the track simply closes. No validator.
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel

from ..base import OfficerToolBase

LossReason = Literal[
    "OUT_OF_RANGE", "OCCLUDED", "JAMMED", "DECONFLICTED", "DESTROYED_TARGET", "OPERATOR_REQUEST"
]


class LoseTrackArgs(BaseModel):
    track_id: UUID
    reason: LossReason


class LoseTrackTool(OfficerToolBase):
    OFFICER_TYPE: ClassVar[str] = "SENSOR"
    VERB: ClassVar[str] = "lose_track"
    EFFECT_FAMILY: ClassVar[str | None] = None

    name: str = "almighty.sensor.lose_track"
    description: str = "End an open track."
    args_schema: type[BaseModel] = LoseTrackArgs

    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, LoseTrackArgs)
        return {"track_id": str(args.track_id), "reason": args.reason}
