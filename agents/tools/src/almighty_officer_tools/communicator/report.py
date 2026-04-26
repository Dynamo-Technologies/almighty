"""Communicator.report — submit a structured report to a higher echelon."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field

from ..base import OfficerToolBase

ReportType = Literal["SITREP", "SPOTREP", "LOGSTAT", "CASEVAC", "INTREP"]
Echelon = Literal["COMPANY", "BATTALION", "BRIGADE", "DIVISION", "WHITE_CELL"]


class ReportArgs(BaseModel):
    report_type: ReportType
    report_payload: dict[str, Any]
    to_echelon: Echelon


class ReportTool(OfficerToolBase):
    OFFICER_TYPE: ClassVar[str] = "COMMUNICATOR"
    VERB: ClassVar[str] = "report"
    EFFECT_FAMILY: ClassVar[str | None] = None

    name: str = "almighty.communicator.report"
    description: str = "Submit a structured report to a higher echelon."
    args_schema: type[BaseModel] = ReportArgs

    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, ReportArgs)
        return {
            "report_type": args.report_type,
            "report_payload": args.report_payload,
            "to_echelon": args.to_echelon,
        }
