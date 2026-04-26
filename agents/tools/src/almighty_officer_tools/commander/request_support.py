"""Commander.request_support — ask higher echelon for an asset."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, model_validator

from ..base import OfficerToolBase

SupportType = Literal["FIRES", "ISR", "MEDEVAC", "LOGISTICS", "EW", "AIR"]
RequestPriority = Literal["LOW", "MEDIUM", "HIGH", "IMMEDIATE"]


class RequestSupportArgs(BaseModel):
    support_type: SupportType
    justification: str = Field(min_length=1, max_length=2000)
    priority: RequestPriority
    target_lat_deg: float | None = Field(default=None, ge=-90, le=90)
    target_lon_deg: float | None = Field(default=None, ge=-180, le=180)
    target_alt_m: float | None = None

    @model_validator(mode="after")
    def _coord_for_fires_medevac(self) -> "RequestSupportArgs":
        needs_coord = self.support_type in ("FIRES", "MEDEVAC")
        has_coord = (
            self.target_lat_deg is not None
            and self.target_lon_deg is not None
            and self.target_alt_m is not None
        )
        if needs_coord and not has_coord:
            raise ValueError(
                f"request_support({self.support_type}) requires target_lat_deg / "
                f"target_lon_deg / target_alt_m"
            )
        return self


class RequestSupportTool(OfficerToolBase):
    OFFICER_TYPE: ClassVar[str] = "COMMANDER"
    VERB: ClassVar[str] = "request_support"
    EFFECT_FAMILY: ClassVar[str | None] = None

    name: str = "almighty.commander.request_support"
    description: str = "Ask higher echelon (or a sister unit) for an asset."
    args_schema: type[BaseModel] = RequestSupportArgs

    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, RequestSupportArgs)
        target = None
        if args.target_lat_deg is not None:
            target = {
                "lat_deg": args.target_lat_deg,
                "lon_deg": args.target_lon_deg,
                "alt_m": args.target_alt_m,
            }
        return {
            "support_type": args.support_type,
            "justification": args.justification,
            "priority": args.priority,
            "target_coordinate": target,
        }
