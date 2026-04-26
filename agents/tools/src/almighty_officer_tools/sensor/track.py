"""Sensor.track — maintain a recurring observation on a previously detected target.

Per WS-105 / WS-108: track has no spatial artifact of its own; it
extends the parent detection's lifetime. No validator call.
"""

from __future__ import annotations

from typing import Any, ClassVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from ..base import OfficerToolBase


class TrackArgs(BaseModel):
    target_entity_id: UUID
    update_rate_hz: float = Field(gt=0)
    track_id: UUID | None = None
    lifetime_s: float | None = Field(default=None, gt=0)


class TrackTool(OfficerToolBase):
    OFFICER_TYPE: ClassVar[str] = "SENSOR"
    VERB: ClassVar[str] = "track"
    EFFECT_FAMILY: ClassVar[str | None] = None

    name: str = "almighty.sensor.track"
    description: str = "Maintain a recurring observation on a previously detected target."
    args_schema: type[BaseModel] = TrackArgs

    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, TrackArgs)
        return {
            "target_entity_id": str(args.target_entity_id),
            "track_id": str(args.track_id or uuid4()),
            "update_rate_hz": args.update_rate_hz,
            "lifetime_s": args.lifetime_s,
        }
