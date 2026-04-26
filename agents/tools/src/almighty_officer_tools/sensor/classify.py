"""Sensor.classify — refine a track into a typed classification.

Always emits a `keyhole_footprint` artifact (per WS-105 § Sensor.classify
and WS-108 § 4.9).
"""

from __future__ import annotations

from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from ..base import OfficerToolBase


class ClassifyArgs(BaseModel):
    track_id: UUID
    classification_label: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    dwell_s: float = Field(gt=0)


class ClassifyTool(OfficerToolBase):
    OFFICER_TYPE: ClassVar[str] = "SENSOR"
    VERB: ClassVar[str] = "classify"
    EFFECT_FAMILY: ClassVar[str | None] = "keyhole_footprint"

    name: str = "almighty.sensor.classify"
    description: str = "Refine a track into a typed classification."
    args_schema: type[BaseModel] = ClassifyArgs

    def _build_validator_params(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, ClassifyArgs)
        return {
            # Tighter footprint scales loosely with dwell; clamp to template
            # range. Real polygon synthesis is a render-time concern.
            "polygon_area_m2": min(50_000.0, max(500.0, args.dwell_s * 100.0)),
        }

    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, ClassifyArgs)
        return {
            "track_id": str(args.track_id),
            "classification_label": args.classification_label,
            "confidence": args.confidence,
            "dwell_s": args.dwell_s,
        }
