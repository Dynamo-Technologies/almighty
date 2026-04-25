"""FastAPI HTTP wrapper around the validator core."""

from __future__ import annotations

from fastapi import FastAPI

from .models import ValidateRequest, ValidationResult
from .validator import Validator

app = FastAPI(
    title="Almighty CZML validator",
    version="0.1.0",
    description="Capability-gated CZML packet validator (WS-202).",
)

_validator = Validator()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/validate", response_model=ValidationResult)
def validate(request: ValidateRequest) -> ValidationResult:
    return _validator.validate(request)
