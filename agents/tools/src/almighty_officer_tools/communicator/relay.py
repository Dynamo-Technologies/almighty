"""Communicator.relay — forward a message between two parties.

Per WS-105: when the entity is airborne AND
``profile.communicator.advertise_corridor`` is True, the relay also
emits a ``uas_corridor`` artifact spanning the relay path. The tool
captures the airborne flag from a runtime arg and the corridor flag
from the profile; both must be true to fire the validator path.
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from ..base import OfficerToolBase

CommsChannel = Literal["VHF", "UHF", "HF", "SATCOM", "DATA"]


class RelayArgs(BaseModel):
    source_entity_id: UUID
    recipient_entity_id: UUID
    channel: CommsChannel
    # The agent declares whether this entity is airborne; the validator
    # gate on uas_corridor only fires if both this and the profile's
    # advertise_corridor are True.
    is_airborne: bool = False
    altitude_band_lower_m: float = Field(gt=0, default=500.0)
    altitude_band_upper_m: float = Field(gt=0, default=2_000.0)
    width_m: float = Field(gt=0, default=2_000.0)


class RelayTool(OfficerToolBase):
    OFFICER_TYPE: ClassVar[str] = "COMMUNICATOR"
    VERB: ClassVar[str] = "relay"
    EFFECT_FAMILY: ClassVar[str | None] = None  # conditional

    name: str = "almighty.communicator.relay"
    description: str = "Forward a message between two parties via this entity."
    args_schema: type[BaseModel] = RelayArgs

    def _effect_family_for(self, args: BaseModel) -> str | None:
        assert isinstance(args, RelayArgs)
        comm = self._ctx.capability_profile.get("communicator", {}) or {}
        if args.is_airborne and comm.get("advertise_corridor", False):
            return "uas_corridor"
        return None

    def _build_validator_params(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, RelayArgs)
        return {
            "altitude_band_lower_m": args.altitude_band_lower_m,
            "altitude_band_upper_m": args.altitude_band_upper_m,
            "width_m": args.width_m,
        }

    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, RelayArgs)
        return {
            "source_entity_id": str(args.source_entity_id),
            "recipient_entity_id": str(args.recipient_entity_id),
            "channel": args.channel,
            "is_airborne": args.is_airborne,
        }
