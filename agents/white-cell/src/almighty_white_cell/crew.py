"""White-cell crew runner — plugs into WS-401's harness.

The white-cell adjudicator is a single agent (not a six-role staff
like blue/red). For the v1 stub, ``run_white_crew(ctx)``:

  1. Builds a real ``crewai.Agent`` for the adjudicator (proper role /
     goal / backstory / tool-set is empty — the adjudicator does not
     issue officer verbs).
  2. Manufactures a synthetic batch of events that would, in a real
     turn, come from blue + red commit logs. v1's batch is hardcoded
     to exercise both DoD scenarios:
       - a contested-effect pair (blue / red events on the same target)
       - a high-stakes destroy event that must hold for human ack.
  3. Calls :func:`adjudicate_events` and stamps the per-event
     decisions into the CrewResult metadata.

The ``ctx`` (tenant_id, scenario_id, turn) flows into the manufactured
events so committed audit rows are correctly namespaced when the v2
integration writes them to the override gateway.
"""

from __future__ import annotations

import time
from typing import Callable
from uuid import UUID, uuid4

from almighty_agent_runtime.crews import CrewContext, CrewResult
from almighty_kernel.dag import KernelEvent
from crewai import Agent

from .adjudicator import Decision, adjudicate_events

ROLE = "White Cell Adjudicator"

GOAL = (
    "Resolve contested or ambiguous effects committed during the "
    "between-turn cycle. Auto-approve routine outcomes; hold high-"
    "stakes events for human ack via the WS-303 override gateway."
)

BACKSTORY = (
    "You are the white-cell adjudicator. You sit outside the blue/red "
    "structure and have cross-tenant visibility within your tenant. "
    "You read the turn's pending events, classify each by stake, and "
    "propose a resolution that the override gateway will either commit "
    "(low/medium) or hold for human review (high). You do not issue "
    "officer verbs yourself; your tool-set is empty. Your output is "
    "the proposed_resolution decisions returned to the harness."
)


def _build_adjudicator_agent() -> Agent:
    """Construct the adjudicator agent shape. v1 deterministic crew
    never calls Crew.kickoff(), so no LLM is configured."""
    return Agent(
        role=ROLE,
        goal=GOAL,
        backstory=BACKSTORY,
        tools=[],  # adjudicator does not issue officer verbs
        allow_delegation=False,
        verbose=False,
        llm=None,
    )


# ---- v1 synthetic event manufacturing ---------------------------------------


def _synthetic_events(crew_ctx: CrewContext) -> list[KernelEvent]:
    """Manufacture a 5-event batch that exercises both DoD scenarios.

    Events 1-3: routine activity (Sensor.detect, Mover.move_to,
    Communicator.send) — should auto-approve.

    Events 4-5: a contested pair — blue Effector.engage and red
    Effector.engage targeting the same entity in the same turn.
    Default contested predicate fires on (c) shared target_entity_id.

    Event 6: a high-stakes destroy — payload.stake='high' (per WS-402
    DestroyTool stamping). Must hold for human ack regardless of
    contested-ness.
    """
    tenant_id = UUID(crew_ctx.tenant_id)
    scenario_id = UUID(crew_ctx.scenario_id)
    turn = crew_ctx.turn

    blue_entity = uuid4()
    red_entity = uuid4()
    contested_target = uuid4()
    civilian_pop_center = uuid4()

    return [
        KernelEvent(
            event_id=uuid4(),
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            turn=turn,
            source_officer_type="SENSOR",
            source_entity_id=blue_entity,
            action_verb="detect",
            payload={"modality": "RADAR", "confidence": 0.9, "range_m": 8000},
            causal_predecessors=[],
        ),
        KernelEvent(
            event_id=uuid4(),
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            turn=turn,
            source_officer_type="MOVER",
            source_entity_id=red_entity,
            action_verb="move_to",
            payload={"target_lat_deg": 36.18, "target_lon_deg": -86.78},
            causal_predecessors=[],
        ),
        KernelEvent(
            event_id=uuid4(),
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            turn=turn,
            source_officer_type="COMMUNICATOR",
            source_entity_id=blue_entity,
            action_verb="send",
            payload={"channel": "VHF", "priority": "ROUTINE"},
            causal_predecessors=[],
        ),
        # Contested pair (events 4 + 5):
        KernelEvent(
            event_id=uuid4(),
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            turn=turn,
            source_officer_type="EFFECTOR",
            source_entity_id=blue_entity,
            action_verb="engage",
            payload={
                "weapon_system": "notional.indirect.medium",
                "target_entity_id": str(contested_target),
                "intent": "NEUTRALIZE",
            },
            causal_predecessors=[],
        ),
        KernelEvent(
            event_id=uuid4(),
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            turn=turn,
            source_officer_type="EFFECTOR",
            source_entity_id=red_entity,
            action_verb="engage",
            payload={
                "weapon_system": "notional.indirect.medium",
                "target_entity_id": str(contested_target),
                "intent": "SUPPRESS_AND_HOLD",
            },
            causal_predecessors=[],
        ),
        # High-stakes destroy (event 6):
        KernelEvent(
            event_id=uuid4(),
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            turn=turn,
            source_officer_type="EFFECTOR",
            source_entity_id=blue_entity,
            action_verb="destroy",
            payload={
                "target_entity_id": str(civilian_pop_center),
                "weapon_system": "notional.indirect.medium",
                "volume_count": 2,
                "justification": "v1 synthetic — DoD high-stakes test",
                "stake": "high",  # per WS-402 DestroyTool stamping
                "target_is_civilian": True,  # exercises the civilian path
            },
            causal_predecessors=[],
        ),
    ]


# ---- Public entry point ------------------------------------------------------


def run_white_crew(crew_ctx: CrewContext) -> CrewResult:
    """Execute one between-turn cycle for the white-cell adjudicator.

    v1: manufactures a synthetic event batch (routine + contested +
    high-stakes), runs adjudication, returns one Decision per event in
    metadata. v2 integration will pull pending events from the harness
    queue (currently empty until WS-401 grows that surface).
    """
    started = time.perf_counter()

    # The adjudicator agent shape is constructed for parity with
    # blue/red crews — even though v1 doesn't invoke Crew.kickoff().
    _agent = _build_adjudicator_agent()

    events = _synthetic_events(crew_ctx)
    decisions: list[Decision] = adjudicate_events(events)

    duration_ms = int((time.perf_counter() - started) * 1000)
    return CrewResult(
        crew="white",
        duration_ms=duration_ms,
        notes=(
            f"v1 deterministic white-cell adjudicator — "
            f"{len(events)} events, "
            f"{sum(1 for d in decisions if d.human_required)} held for human ack"
        ),
        metadata={
            "tenant_id": crew_ctx.tenant_id,
            "scenario_id": crew_ctx.scenario_id,
            "turn": crew_ctx.turn,
            "events_in": len(events),
            "events_in_ids": [str(e.event_id) for e in events],
            "decisions": [
                {
                    "event_id": str(d.event_id),
                    "action_verb": d.action_verb,
                    "source_officer_type": d.source_officer_type,
                    "stake": d.stake,
                    "outcome": d.outcome,
                    "human_required": d.human_required,
                    "contested": d.contested,
                    "rationale": d.rationale,
                    "conflicts_with": [str(x) for x in d.conflicts_with],
                }
                for d in decisions
            ],
        },
    )


# Convenience export for the eventual WS-401 integration. The harness's
# WHITE_CREWS["default"] swap should land alongside BLUE_RUNNER +
# RED_RUNNER once all three crews are ready to go live together.
WHITE_RUNNER: Callable[[CrewContext], CrewResult] = run_white_crew
