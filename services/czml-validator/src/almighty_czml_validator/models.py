from typing import Any

from pydantic import BaseModel, Field


class ValidateRequest(BaseModel):
    """Input to validator. Fields match the runbook signature for WS-202."""

    template_id: str = Field(description="Template to validate against, e.g. 'jamming-circle'.")
    template_version: int = Field(default=1, ge=1)
    params: dict[str, Any] = Field(
        description="Post-substitution param values keyed by template param name."
    )
    agent_id: str = Field(description="Caller identity; logged for correlation.")
    capability_profile: dict[str, Any] = Field(
        description="The full WS-106 / WS-107 capability profile JSON."
    )


class ValidationResult(BaseModel):
    accepted: bool
    reasons: list[str] = Field(default_factory=list)

    @classmethod
    def accept(cls) -> "ValidationResult":
        return cls(accepted=True, reasons=[])

    @classmethod
    def reject(cls, reason: str) -> "ValidationResult":
        return cls(accepted=False, reasons=[reason])
