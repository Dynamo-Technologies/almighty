"""Adapter result types.

The adapter's output is a tagged-union per input event:

  ACCEPTED  - validator accepted; the CZML packet is ready to publish.
  REJECTED  - validator rejected; emit a `czml_rejected` audit event.
  SKIPPED   - event is not spatial / no family handler matches; ignore.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID


class ResultKind(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class EntityPosition:
    """A point in WGS-84 + ECEF, supplied by the caller's entity-position
    lookup callback. v1 callers fabricate these; v2 wires the entity
    table from the control-plane DB."""

    lat_deg: float
    lon_deg: float
    alt_m: float


@dataclass
class AdapterResult:
    """Tagged union — exactly one of `packet` (ACCEPTED) or `reason`
    (REJECTED / SKIPPED) is set."""

    kind: ResultKind
    event_id: UUID
    family: str | None
    packet: dict[str, Any] | None = None
    reason: str | None = None
    validator_params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def accepted(
        cls, event_id: UUID, family: str, packet: dict[str, Any], validator_params: dict[str, Any]
    ) -> "AdapterResult":
        return cls(
            kind=ResultKind.ACCEPTED,
            event_id=event_id,
            family=family,
            packet=packet,
            validator_params=validator_params,
        )

    @classmethod
    def rejected(
        cls, event_id: UUID, family: str, reason: str, validator_params: dict[str, Any]
    ) -> "AdapterResult":
        return cls(
            kind=ResultKind.REJECTED,
            event_id=event_id,
            family=family,
            reason=reason,
            validator_params=validator_params,
        )

    @classmethod
    def skipped(cls, event_id: UUID, reason: str) -> "AdapterResult":
        return cls(kind=ResultKind.SKIPPED, event_id=event_id, family=None, reason=reason)
