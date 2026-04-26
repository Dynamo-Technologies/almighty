"""Sensor.detect — identify a previously unobserved target.

Spatial artifact emitted depends on modality, per WS-108 § 6.1:

  EO_IR        -> none in v1 (no template)
  RF           -> ew_cone
  RADAR        -> radar_fan
  ACOUSTIC     -> masint_cell
  SEISMIC      -> masint_cell
  MASINT_MULTI -> masint_cell
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from ..base import OfficerToolBase

Modality = Literal["EO_IR", "RF", "RADAR", "ACOUSTIC", "SEISMIC", "MASINT_MULTI"]

_FAMILY_BY_MODALITY: dict[Modality, str | None] = {
    "EO_IR": None,
    "RF": "ew_cone",
    "RADAR": "radar_fan",
    "ACOUSTIC": "masint_cell",
    "SEISMIC": "masint_cell",
    "MASINT_MULTI": "masint_cell",
}


class DetectArgs(BaseModel):
    target_entity_id: UUID
    modality: Modality
    confidence: float = Field(ge=0.0, le=1.0)
    range_m: float = Field(gt=0)
    czml_template: str | None = None


class DetectTool(OfficerToolBase):
    OFFICER_TYPE: ClassVar[str] = "SENSOR"
    VERB: ClassVar[str] = "detect"
    # EFFECT_FAMILY resolved per-call from modality.
    EFFECT_FAMILY: ClassVar[str | None] = None

    name: str = "almighty.sensor.detect"
    description: str = "Identify a previously unobserved target."
    args_schema: type[BaseModel] = DetectArgs

    def _effect_family_for(self, args: BaseModel) -> str | None:
        assert isinstance(args, DetectArgs)
        return _FAMILY_BY_MODALITY[args.modality]

    def _build_validator_params(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, DetectArgs)
        family = _FAMILY_BY_MODALITY[args.modality]
        # Each family expects different params; keep this minimal — the
        # validator only checks template `capability_constraints` keys.
        if family == "ew_cone":
            return {
                "azimuth_deg": 0.0,
                "beamwidth_deg": 30.0,
                "effective_range_m": args.range_m,
            }
        if family == "radar_fan":
            return {
                "azimuth_deg": 0.0,
                "sweep_arc_deg": 60.0,
                "range_m": args.range_m,
            }
        if family == "masint_cell":
            return {
                "polygon_area_m2": 50_000.0,
                "dwell_s": 600.0,
            }
        # EO_IR has no validator path — _effect_family_for returned None,
        # so this method is never called.
        raise AssertionError(f"unreachable: family={family}")

    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, DetectArgs)
        return {
            "target_entity_id": str(args.target_entity_id),
            "modality": args.modality,
            "confidence": args.confidence,
            "range_m": args.range_m,
            "czml_template": args.czml_template,
        }
