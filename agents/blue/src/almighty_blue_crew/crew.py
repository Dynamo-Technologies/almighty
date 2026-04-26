"""Blue battalion crew orchestration (WS-403).

S2 / CO A / CO B / CO C / S6 still run as scripted deterministic
between-turn steps in the WS-105 order:

    S2  → S3  → companies (A → B → C)  → S6

S3 is LLM-driven via Gemma 4 26B-A4B on spark-763d (per the hackathon
demo spec): the role reads PyRapide's causal-order topological view as
its situation report, decides via Crew.kickoff(), and the resulting
commit cites the situation-report events as causal_predecessors. If
the LLM call fails, S3 falls back to the v1 deterministic pair so the
demo never hard-stops on stage.

Each agent gets its own ``OfficerToolContext`` with its own
``agent_entity_id`` so events committed to the namespaced DAG are
correctly attributed per-role.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Final, Union
from uuid import UUID, uuid4

from almighty_agent_runtime.crews import CrewContext, CrewResult
from almighty_agent_runtime.llm_clients import build_blue_llm
from almighty_agent_runtime.llm_step import run_llm_role_step
from almighty_czml_validator import Validator
from almighty_kernel.dag import NamespacedDag
from almighty_officer_tools import OfficerToolContext, build_all_tools
from almighty_officer_tools.base import OfficerToolBase
from crewai import Agent

from . import co_a, co_b, co_c, s2, s3, s6
from .doctrine import (
    COMPANY_A_POSITION,
    COMPANY_B_POSITION,
    COMPANY_C_POSITION,
    EAST_BANK_NAMED_AREA_OF_INTEREST,
    WEST_BANK_BN_HQ,
    WEST_BANK_OBSERVATION_POST,
)
from .profile import load_us_bct_profile

# Roles in execution order. Mirrors S2 → S3 → companies → S6.
_ROLE_MODULES = [s2, s3, co_a, co_b, co_c, s6]


@dataclass
class _RoleBinding:
    """Per-role bundle: the CrewAI Agent shape + the bound tool subset
    + the OfficerToolContext so the deterministic script can read
    agent_entity_id when assembling event payloads."""

    name: str
    agent: Agent
    ctx: OfficerToolContext
    tools: dict[str, OfficerToolBase]


def _build_role(
    spec_module: Any,
    *,
    crew_ctx: CrewContext,
    capability_profile: dict[str, Any],
    kernel_dag: NamespacedDag,
    validator: Validator,
) -> _RoleBinding:
    """Construct one role's Agent + tool context from a spec module."""
    agent_entity_id = uuid4()
    ctx = OfficerToolContext(
        tenant_id=UUID(crew_ctx.tenant_id),
        scenario_id=UUID(crew_ctx.scenario_id),
        turn=crew_ctx.turn,
        agent_entity_id=agent_entity_id,
        capability_profile=capability_profile,
        kernel_dag=kernel_dag,
        validator=validator,
    )
    all_tools = build_all_tools(ctx)
    scoped_tools = {
        verb: tool for verb, tool in all_tools.items() if verb in spec_module.ALLOWED_VERBS
    }
    agent = Agent(
        role=spec_module.ROLE,
        goal=spec_module.GOAL,
        backstory=spec_module.BACKSTORY,
        tools=list(scoped_tools.values()),
        allow_delegation=False,
        verbose=False,
        # No LLM is configured: the v1 crew is deterministic and never
        # invokes Crew.kickoff(). Agent construction works without an
        # LLM as long as kickoff() is never called.
        llm=None,
    )
    return _RoleBinding(
        name=spec_module.__name__.rsplit(".", 1)[-1],
        agent=agent,
        ctx=ctx,
        tools=scoped_tools,
    )


# ---------------------------------------------------------------------------
# Deterministic between-turn script
# ---------------------------------------------------------------------------

# A single "step" either calls one tool (returning a single result dict)
# or — for LLM-driven roles — drives one or more tool calls via CrewAI
# (returning a LIST of result dicts, one per committed event). The main
# loop in ``run_blue_crew`` handles both shapes.

_StepResult = Union[dict[str, Any], list[dict[str, Any]]]
_StepFn = Callable[[dict[str, "_RoleBinding"]], _StepResult]


def _step_s2_detect(roles: dict[str, _RoleBinding]) -> dict[str, Any]:
    s2_role = roles["s2"]
    return s2_role.tools["detect"]._run(
        target_entity_id=uuid4(),  # synthetic red track id
        modality="RADAR",
        confidence=0.85,
        range_m=12_000.0,
    )


def _step_s2_classify(roles: dict[str, _RoleBinding]) -> dict[str, Any]:
    s2_role = roles["s2"]
    return s2_role.tools["classify"]._run(
        track_id=uuid4(),
        classification_label="notional.air.uas.medium",
        confidence=0.78,
        dwell_s=15.0,
    )


def _step_s3_issue_order_to_a(roles: dict[str, _RoleBinding]) -> dict[str, Any]:
    s3_role = roles["s3"]
    co_a_role = roles["co_a"]
    return s3_role.tools["issue_order"]._run(
        order_type="MOVE",
        order_payload={
            "waypoints": [
                {
                    "lat_deg": COMPANY_A_POSITION.lat_deg,
                    "lon_deg": COMPANY_A_POSITION.lon_deg,
                    "alt_m": COMPANY_A_POSITION.alt_m,
                }
            ],
        },
        to_entity_id=co_a_role.ctx.agent_entity_id,
        priority="MEDIUM",
    )


def _step_s3_request_isr(roles: dict[str, _RoleBinding]) -> dict[str, Any]:
    s3_role = roles["s3"]
    return s3_role.tools["request_support"]._run(
        support_type="ISR",
        justification="confirm red UAS overflight pattern",
        priority="HIGH",
    )


def _step_co_a_assume_posture(roles: dict[str, _RoleBinding]) -> dict[str, Any]:
    return roles["co_a"].tools["assume_posture"]._run(posture="DUG_IN")


def _step_co_a_send_sitrep(roles: dict[str, _RoleBinding]) -> dict[str, Any]:
    bn_hq = roles["s3"].ctx.agent_entity_id  # CO A reports to S3
    return roles["co_a"].tools["send"]._run(
        channel="VHF",
        message_payload={
            "type": "SITREP",
            "line1": "in position; no contact",
        },
        recipient_entity_id=bn_hq,
        priority="ROUTINE",
    )


def _step_co_b_halt(roles: dict[str, _RoleBinding]) -> dict[str, Any]:
    return roles["co_b"].tools["halt"]._run()


def _step_co_b_suppress(roles: dict[str, _RoleBinding]) -> dict[str, Any]:
    return roles["co_b"].tools["suppress"]._run(
        weapon_system="notional.indirect.medium",
        duration_s=60.0,
        rate_per_min=4.0,
        target_lat_deg=EAST_BANK_NAMED_AREA_OF_INTEREST.lat_deg,
        target_lon_deg=EAST_BANK_NAMED_AREA_OF_INTEREST.lon_deg,
        target_alt_m=EAST_BANK_NAMED_AREA_OF_INTEREST.alt_m,
        range_m=8_000.0,
        time_of_flight_s=18.0,
    )


def _step_co_c_move(roles: dict[str, _RoleBinding]) -> dict[str, Any]:
    return roles["co_c"].tools["move_to"]._run(
        target_lat_deg=COMPANY_C_POSITION.lat_deg + 0.005,  # slight repositioning N
        target_lon_deg=COMPANY_C_POSITION.lon_deg,
        target_alt_m=COMPANY_C_POSITION.alt_m,
        speed_mps=10.0,
    )


def _step_s6_send_to_brigade(roles: dict[str, _RoleBinding]) -> dict[str, Any]:
    return roles["s6"].tools["send"]._run(
        channel="HF",
        message_payload={"type": "comms-status", "status": "green"},
        recipient_role="BRIGADE_S6",
        priority="ROUTINE",
    )


def _step_s6_report(roles: dict[str, _RoleBinding]) -> dict[str, Any]:
    return roles["s6"].tools["report"]._run(
        report_type="SITREP",
        report_payload={
            "comms": "nominal",
            "ew_observed": False,
            "channels_in_use": ["VHF", "HF"],
        },
        to_echelon="BRIGADE",
    )


def _step_s3_llm_decide(roles: dict[str, _RoleBinding]) -> list[dict[str, Any]]:
    """LLM-driven S3 decision step (Gemma 4 26B-A4B on spark-763d).

    Replaces the deterministic _step_s3_issue_order_to_a +
    _step_s3_request_isr pair. S3 reads the situation report (S2's
    detect + classify events from earlier in this cycle) and decides
    which orders to issue. Committed events carry causal_predecessors
    back to the events the LLM actually saw.

    Falls back to the deterministic pair if the LLM call raises so the
    demo never hard-fails on stage.

    Returns a list of step dicts (one per committed event) so the main
    loop can extend ``step_outcomes`` uniformly.
    """
    s3_role = roles["s3"]

    try:
        llm = build_blue_llm()
        # The helper returns one result dict per tool call. Each dict is
        # exactly what OfficerToolBase._run produced, including
        # causal_predecessors as a string list — don't go through
        # dag.read() because the kernel's _reconstruct drops predecessors.
        results = run_llm_role_step(
            ctx=s3_role.ctx,
            agent=s3_role.agent,
            llm=llm,
            task_description=(
                "You are the battalion S3 at the Cumberland River crossing. "
                "Based on the situation report, decide what orders to issue "
                "and what support to request. Use issue_order to direct "
                "Companies A/B/C; use request_support for ISR/EW/fires from "
                "higher echelon. Keep your action minimal — at most one "
                "issue_order and one request_support per turn."
            ),
            expected_output=(
                "Tool calls only. No prose. Pick one or two of: "
                "issue_order(...) or request_support(...)."
            ),
        )
        if not results:
            # Gemma replied with text only — fall through to the fallback
            # so the demo always commits some events for the renderer.
            raise RuntimeError("LLM returned no tool calls")
        return [
            {
                "step": f"s3.llm_decide.{r.get('verb')}",
                "event_id": r.get("event_id"),
                "verb": r.get("verb"),
                "officer_type": r.get("officer_type"),
                "source_entity_id": r.get("source_entity_id"),
                "validator": r.get("validator"),
                "causal_predecessors": r.get("causal_predecessors", []),
                "llm_driven": True,
            }
            for r in results
        ]
    except Exception as exc:
        # Demo safety net: fall back to the deterministic pair so the
        # event chain still produces something for the renderer.
        s3_role.ctx.causal_predecessors = []  # defense-in-depth
        results = [
            _step_s3_issue_order_to_a(roles),
            _step_s3_request_isr(roles),
        ]
        for r in results:
            r["step"] = f"s3.llm_decide_fallback.{r['verb']}"
            r["llm_driven"] = False
            r["fallback_reason"] = f"{type(exc).__name__}: {exc}"
        return results


# Order matters: S2 → S3 (LLM) → companies (A → B → C) → S6.
_BETWEEN_TURN_SCRIPT: Final[list[tuple[str, _StepFn]]] = [
    ("s2.detect", _step_s2_detect),
    ("s2.classify", _step_s2_classify),
    ("s3.llm_decide", _step_s3_llm_decide),
    ("co_a.assume_posture", _step_co_a_assume_posture),
    ("co_a.send", _step_co_a_send_sitrep),
    ("co_b.halt", _step_co_b_halt),
    ("co_b.suppress", _step_co_b_suppress),
    ("co_c.move_to", _step_co_c_move),
    ("s6.send", _step_s6_send_to_brigade),
    ("s6.report", _step_s6_report),
]


def _orientation_anchors() -> dict[str, dict[str, float]]:
    """Diagnostic hook for the README — surfaces the geographic anchors
    the v1 script keys off of so a reader knows what 'BLUE-OP-1', etc.,
    map to without grepping through doctrine.py."""
    return {
        "bn_hq": {"lat": WEST_BANK_BN_HQ.lat_deg, "lon": WEST_BANK_BN_HQ.lon_deg},
        "op": {
            "lat": WEST_BANK_OBSERVATION_POST.lat_deg,
            "lon": WEST_BANK_OBSERVATION_POST.lon_deg,
        },
        "co_a": {"lat": COMPANY_A_POSITION.lat_deg, "lon": COMPANY_A_POSITION.lon_deg},
        "co_b": {"lat": COMPANY_B_POSITION.lat_deg, "lon": COMPANY_B_POSITION.lon_deg},
        "co_c": {"lat": COMPANY_C_POSITION.lat_deg, "lon": COMPANY_C_POSITION.lon_deg},
        "nai_east": {
            "lat": EAST_BANK_NAMED_AREA_OF_INTEREST.lat_deg,
            "lon": EAST_BANK_NAMED_AREA_OF_INTEREST.lon_deg,
        },
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_blue_crew(crew_ctx: CrewContext) -> CrewResult:
    """Execute one between-turn cycle for the blue battalion crew.

    Self-contained: instantiates a fresh kernel DAG and validator,
    builds the six agents bound to the us-bct profile, and runs the
    deterministic 11-step script. Every step's tool call commits a
    KernelEvent through ``NamespacedDag.commit()``.

    Returns a :class:`CrewResult` with the events_committed count and
    the per-step outcomes in metadata. Any step raising ``ToolError``
    aborts the cycle and propagates to the caller.
    """
    started = time.perf_counter()
    profile = load_us_bct_profile()
    kernel_dag = NamespacedDag()
    validator = Validator()

    bindings = {
        m.__name__.rsplit(".", 1)[-1]: _build_role(
            m,
            crew_ctx=crew_ctx,
            capability_profile=profile,
            kernel_dag=kernel_dag,
            validator=validator,
        )
        for m in _ROLE_MODULES
    }

    step_outcomes: list[dict[str, Any]] = []
    for label, step_fn in _BETWEEN_TURN_SCRIPT:
        result = step_fn(bindings)
        if isinstance(result, list):
            # LLM-driven step returns one entry per committed event; the
            # entries already have their own "step" labels.
            step_outcomes.extend(result)
        else:
            step_outcomes.append({"step": label, **result})

    duration_ms = int((time.perf_counter() - started) * 1000)

    return CrewResult(
        crew="blue",
        duration_ms=duration_ms,
        notes=f"v1 deterministic blue crew — {len(step_outcomes)} events committed",
        metadata={
            "tenant_id": crew_ctx.tenant_id,
            "scenario_id": crew_ctx.scenario_id,
            "turn": crew_ctx.turn,
            "events_committed": len(step_outcomes),
            "steps": step_outcomes,
            "validator_rejections": 0,  # any reject would have raised before reaching here
            "anchors": _orientation_anchors(),
        },
    )


# Convenience export so WS-401 can register `BLUE_CREWS["default"] =
# BLUE_RUNNER` in a follow-up integration ticket.
BLUE_RUNNER: Callable[[CrewContext], CrewResult] = run_blue_crew
