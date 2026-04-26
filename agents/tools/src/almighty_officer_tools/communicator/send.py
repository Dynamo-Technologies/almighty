"""Communicator.send — transmit a message to a recipient (non-spatial)."""

from __future__ import annotations

from typing import Any, ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ..base import OfficerToolBase

CommsChannel = Literal["VHF", "UHF", "HF", "SATCOM", "DATA"]
CommsPriority = Literal["ROUTINE", "PRIORITY", "IMMEDIATE", "FLASH"]


class SendArgs(BaseModel):
    channel: CommsChannel
    message_payload: dict[str, Any]
    recipient_entity_id: UUID | None = None
    recipient_role: str | None = None
    priority: CommsPriority = "ROUTINE"

    @model_validator(mode="after")
    def _recipient_xor(self) -> "SendArgs":
        if (self.recipient_entity_id is None) == (self.recipient_role is None):
            raise ValueError(
                "send requires exactly one of recipient_entity_id or recipient_role"
            )
        return self


class SendTool(OfficerToolBase):
    OFFICER_TYPE: ClassVar[str] = "COMMUNICATOR"
    VERB: ClassVar[str] = "send"
    EFFECT_FAMILY: ClassVar[str | None] = None

    name: str = "almighty.communicator.send"
    description: str = "Transmit a message to a recipient."
    args_schema: type[BaseModel] = SendArgs

    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, SendArgs)
        return {
            "channel": args.channel,
            "message_payload": args.message_payload,
            "recipient_entity_id": (
                str(args.recipient_entity_id) if args.recipient_entity_id else None
            ),
            "recipient_role": args.recipient_role,
            "priority": args.priority,
        }
