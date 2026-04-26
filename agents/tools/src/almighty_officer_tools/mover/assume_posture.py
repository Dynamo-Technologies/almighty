"""Mover.assume_posture — change tactical posture.

Validator-side: the posture-transition matrix is enforced by the
capability-profile validator (WS-202 v2; not in scope here). v1 commits
the event and lets the adjudicator (WS-405) reject if the target posture
is not in the profile's `posture_transitions`.
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field

from ..base import OfficerToolBase

Posture = Literal["HALTED", "MOUNTED", "DISMOUNTED", "DUG_IN", "ALERT", "REST"]


class AssumePostureArgs(BaseModel):
    posture: Posture
    transition_s: float | None = Field(default=None, gt=0)


class AssumePostureTool(OfficerToolBase):
    OFFICER_TYPE: ClassVar[str] = "MOVER"
    VERB: ClassVar[str] = "assume_posture"
    EFFECT_FAMILY: ClassVar[str | None] = None

    name: str = "almighty.mover.assume_posture"
    description: str = "Change the entity's tactical posture."
    args_schema: type[BaseModel] = AssumePostureArgs

    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, AssumePostureArgs)
        return {"posture": args.posture, "transition_s": args.transition_s}
