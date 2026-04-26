"""Commander.delegate — hand subordinate authority for a subset of verbs.

Per WS-105: ``delegated_verbs ⊆ this_entity.capability.action_verbs_available``.
The base capability gate fires on this verb itself; the subset check on
delegated_verbs happens here.
"""

from __future__ import annotations

from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from ..base import OfficerToolBase
from ..context import ToolError


class DelegateArgs(BaseModel):
    to_entity_id: UUID
    delegated_verbs: list[str] = Field(min_length=1)
    ttl_turns: int = Field(ge=1)


class DelegateTool(OfficerToolBase):
    OFFICER_TYPE: ClassVar[str] = "COMMANDER"
    VERB: ClassVar[str] = "delegate"
    EFFECT_FAMILY: ClassVar[str | None] = None

    name: str = "almighty.commander.delegate"
    description: str = "Hand subordinate authority for a subset of verbs to another entity."
    args_schema: type[BaseModel] = DelegateArgs

    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, DelegateArgs)
        owned = set(self._ctx.capability_profile.get("action_verbs_available", []))
        bad = sorted(set(args.delegated_verbs) - owned)
        if bad:
            raise ToolError(
                f"delegate: cannot delegate verbs not in own authority: {bad}"
            )
        return {
            "to_entity_id": str(args.to_entity_id),
            "delegated_verbs": list(args.delegated_verbs),
            "ttl_turns": args.ttl_turns,
        }
