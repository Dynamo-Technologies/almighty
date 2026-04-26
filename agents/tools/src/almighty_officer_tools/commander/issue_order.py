"""Commander.issue_order — direct a subordinate to take action."""

from __future__ import annotations

from typing import Any, ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, model_validator

from ..base import OfficerToolBase

OrderType = Literal["MOVE", "ATTACK", "DEFEND", "RECON", "SUPPORT", "WITHDRAW"]
OrderPriority = Literal["LOW", "MEDIUM", "HIGH"]
Echelon = Literal["COMPANY", "BATTALION", "BRIGADE", "DIVISION", "WHITE_CELL"]


class IssueOrderArgs(BaseModel):
    order_type: OrderType
    order_payload: dict[str, Any]
    to_entity_id: UUID | None = None
    to_echelon: Echelon | None = None
    priority: OrderPriority = "MEDIUM"

    @model_validator(mode="after")
    def _to_xor(self) -> "IssueOrderArgs":
        if (self.to_entity_id is None) == (self.to_echelon is None):
            raise ValueError(
                "issue_order requires exactly one of to_entity_id or to_echelon"
            )
        return self


class IssueOrderTool(OfficerToolBase):
    OFFICER_TYPE: ClassVar[str] = "COMMANDER"
    VERB: ClassVar[str] = "issue_order"
    EFFECT_FAMILY: ClassVar[str | None] = None

    name: str = "almighty.commander.issue_order"
    description: str = "Direct a subordinate to take action."
    args_schema: type[BaseModel] = IssueOrderArgs

    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, IssueOrderArgs)
        return {
            "order_type": args.order_type,
            "order_payload": args.order_payload,
            "to_entity_id": str(args.to_entity_id) if args.to_entity_id else None,
            "to_echelon": args.to_echelon,
            "priority": args.priority,
        }
