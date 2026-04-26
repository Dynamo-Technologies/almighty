"""Commander.escalate — push a decision to higher echelon.

Per WS-105 and the better-late-than-never doc: `to_echelon` MUST be
strictly higher than the issuing entity's echelon. The check happens
here using ``self._ctx.capability_profile.commander.echelon`` as the
issuing echelon.
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from ..base import OfficerToolBase
from ..context import ToolError

EscalationSeverity = Literal["ROUTINE", "PRIORITY", "FLASH"]
Echelon = Literal["COMPANY", "BATTALION", "BRIGADE", "DIVISION", "WHITE_CELL"]

_ECHELON_RANK: dict[Echelon, int] = {
    "COMPANY": 1,
    "BATTALION": 2,
    "BRIGADE": 3,
    "DIVISION": 4,
    "WHITE_CELL": 5,
}


class EscalateArgs(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
    severity: EscalationSeverity
    to_echelon: Echelon
    references: list[UUID] = Field(default_factory=list)


class EscalateTool(OfficerToolBase):
    OFFICER_TYPE: ClassVar[str] = "COMMANDER"
    VERB: ClassVar[str] = "escalate"
    EFFECT_FAMILY: ClassVar[str | None] = None

    name: str = "almighty.commander.escalate"
    description: str = "Push a decision to a strictly higher echelon."
    args_schema: type[BaseModel] = EscalateArgs

    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, EscalateArgs)
        commander = self._ctx.capability_profile.get("commander") or {}
        own_ech = commander.get("echelon")
        if own_ech is None or own_ech not in _ECHELON_RANK:
            raise ToolError(
                "escalate: profile.commander.echelon missing or unknown — "
                "cannot determine 'strictly higher' rank"
            )
        if _ECHELON_RANK[args.to_echelon] <= _ECHELON_RANK[own_ech]:
            raise ToolError(
                f"escalate: to_echelon='{args.to_echelon}' is not strictly higher "
                f"than own echelon='{own_ech}'"
            )
        return {
            "reason": args.reason,
            "severity": args.severity,
            "to_echelon": args.to_echelon,
            "references": [str(r) for r in args.references],
        }
