"""Effector.destroy — remove a target from the scenario.

Always high-stakes per WS-105 § Effector.destroy and WS-108 § 4.6
(`always-contested` flow). The override gateway floors this at
`always-contested`; the tool itself proceeds to commit and the
adjudicator (WS-405) holds it for human ack downstream.

The DoD-required `justification` field is captured on the event payload
for AAR.
"""

from __future__ import annotations

from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from ..base import OfficerToolBase


class DestroyArgs(BaseModel):
    target_entity_id: UUID
    weapon_system: str = Field(min_length=1)
    volume_count: int = Field(ge=1)
    justification: str = Field(min_length=1, max_length=2000)
    range_m: float = Field(gt=0)
    time_of_flight_s: float = Field(ge=0)
    dispersion_ellipse_a_m: float = Field(gt=0, default=50.0)
    dispersion_ellipse_b_m: float = Field(gt=0, default=50.0)


class DestroyTool(OfficerToolBase):
    OFFICER_TYPE: ClassVar[str] = "EFFECTOR"
    VERB: ClassVar[str] = "destroy"
    EFFECT_FAMILY: ClassVar[str | None] = "indirect_fire_arc"

    name: str = "almighty.effector.destroy"
    description: str = "Remove a target from the scenario. Always high-stakes (human review)."
    args_schema: type[BaseModel] = DestroyArgs

    def _build_validator_params(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, DestroyArgs)
        return {
            "range_m": args.range_m,
            "time_of_flight_s": args.time_of_flight_s,
            "dispersion_ellipse_a_m": args.dispersion_ellipse_a_m,
            "dispersion_ellipse_b_m": args.dispersion_ellipse_b_m,
        }

    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, DestroyArgs)
        return {
            "target_entity_id": str(args.target_entity_id),
            "weapon_system": args.weapon_system,
            "volume_count": args.volume_count,
            "justification": args.justification,
            "range_m": args.range_m,
            "time_of_flight_s": args.time_of_flight_s,
            # Marker for downstream WS-405 adjudicator to flag human_required.
            "stake": "high",
        }
