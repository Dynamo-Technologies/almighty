"""Mover.halt — stop motion immediately. No parameters."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel

from ..base import OfficerToolBase


class HaltArgs(BaseModel):
    pass


class HaltTool(OfficerToolBase):
    OFFICER_TYPE: ClassVar[str] = "MOVER"
    VERB: ClassVar[str] = "halt"
    EFFECT_FAMILY: ClassVar[str | None] = None

    name: str = "almighty.mover.halt"
    description: str = "Stop motion immediately."
    args_schema: type[BaseModel] = HaltArgs

    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        del args
        return {}
