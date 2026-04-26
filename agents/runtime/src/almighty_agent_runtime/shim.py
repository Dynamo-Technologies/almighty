"""HTTP shim that the EC2 control-plane calls to drive a between-turn cycle.

POST /run-turn → runs blue + red crews concurrently, returns the
flattened list of events as JSON. Deployed inside the existing CrewAI
container on spark-763d via a bind-mount of the almighty repo and a
CMD override (see agents/runtime/spark/run-worker.sh).

The shim is deliberately thin: the heavy lifting (LLM calls,
PyRapide situation reports, predecessor auto-linking) all lives in
the crew code. The shim's job is the parallel dispatch and the wire
serialization.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from almighty_blue_crew.crew import run_blue_crew
from almighty_red_crew.crew import run_red_crew

from .crews import CrewContext


app = FastAPI(title="almighty-spark-worker")


class RunTurnRequest(BaseModel):
    tenant_id: str = Field(..., description="UUID of the demo tenant")
    scenario_id: str = Field(..., description="UUID of the scenario")
    turn: int = Field(..., ge=0, description="Turn number to run")


class RunTurnResponse(BaseModel):
    turn: int
    blue_duration_ms: int
    red_duration_ms: int
    events: list[dict[str, Any]]


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.post("/run-turn", response_model=RunTurnResponse)
async def run_turn(req: RunTurnRequest) -> RunTurnResponse:
    crew_ctx = CrewContext(
        tenant_id=req.tenant_id,
        scenario_id=req.scenario_id,
        turn=req.turn,
    )

    # Run both crews in parallel via asyncio.to_thread — the crew
    # functions are sync (they call CrewAI which calls the LLM
    # synchronously), so we offload them to threads.
    blue_task = asyncio.to_thread(run_blue_crew, crew_ctx)
    red_task = asyncio.to_thread(run_red_crew, crew_ctx)
    blue_result, red_result = await asyncio.gather(blue_task, red_task)

    events: list[dict[str, Any]] = []
    events.extend(_events_from_result(blue_result, side="blue", req=req))
    events.extend(_events_from_result(red_result, side="red", req=req))

    return RunTurnResponse(
        turn=req.turn,
        blue_duration_ms=blue_result.duration_ms,
        red_duration_ms=red_result.duration_ms,
        events=events,
    )


def _events_from_result(result: Any, *, side: str, req: RunTurnRequest) -> list[dict[str, Any]]:
    """Convert CrewResult.metadata['steps'] into the wire-format events list.

    Each step dict already carries event_id, verb, officer_type, validator,
    and causal_predecessors (set by OfficerToolBase._run). We add the side
    label and stamp tenant/scenario/turn for the control-plane's convenience.
    """
    out: list[dict[str, Any]] = []
    for step in result.metadata.get("steps", []):
        out.append({
            "side": side,
            "step": step.get("step"),
            "event_id": step.get("event_id"),
            "verb": step.get("verb"),
            "officer_type": step.get("officer_type"),
            "source_entity_id": step.get("source_entity_id"),
            "validator": step.get("validator"),
            "tenant_id": req.tenant_id,
            "scenario_id": req.scenario_id,
            "turn": req.turn,
            "causal_predecessors": step.get("causal_predecessors", []),
            "llm_driven": step.get("llm_driven", False),
        })
    return out
