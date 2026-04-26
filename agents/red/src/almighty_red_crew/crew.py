"""Red OpFor crew orchestration (WS-404).

Mirror of the blue crew (WS-403) shape, with three differences:

1. **Doctrine flavor.** ``run_red_crew(ctx, doctrine=...)`` selects
   one of ``peer`` / ``near-peer`` / ``hybrid``. The flavor swaps
   per-role goal / backstory text and chooses the bound capability
   profile (``peer.json`` / ``near-peer.json`` / ``hybrid-irregular.json``).

2. **Uncertainty bands exercised.** When Co B builds its indirect-fire
   step, it resolves the doctrine-appropriate band on
   ``effector.weapon_systems[<id>].effective_range_m``, computes the
   upper-with-band reasoning value, and then commits the
   ``min(reasoning, profile_max)`` capped value. Both numbers are
   recorded on the step result for the test to assert.

3. **Hybrid lacks Commander verbs.** Peer / near-peer profiles have
   all four; the hybrid profile has none. The script substitutes
   Communicator.send for the S3 issue_order step in hybrid, and skips
   request_support entirely. Total step count: 11 for peer / near-peer,
   10 for hybrid.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Union
from uuid import UUID, uuid4

from almighty_agent_runtime.crews import CrewContext, CrewResult
from almighty_agent_runtime.llm_clients import build_red_llm
from almighty_agent_runtime.llm_step import run_llm_role_step
from almighty_czml_validator import Validator
from almighty_kernel.dag import NamespacedDag
from almighty_officer_tools import OfficerToolContext, build_all_tools
from almighty_officer_tools.base import OfficerToolBase
from crewai import Agent

from . import co_a, co_b, co_c, s2, s3, s6
from .doctrine import (
    Doctrine,
    RED_COMPANY_A_POSITION,
    RED_COMPANY_C_POSITION,
    WEST_BANK_OBJECTIVE_AREA,
    assemble_backstory,
    assemble_goal,
    select_doctrine,
)
from .profile import load_profile
from .uncertainty import UncertaintyResolution, resolve_uncertain_value

_ROLE_MODULES = [s2, s3, co_a, co_b, co_c, s6]


@dataclass
class _RoleBinding:
    name: str
    agent: Agent
    ctx: OfficerToolContext
    tools: dict[str, OfficerToolBase]


def _build_role(
    spec_module: Any,
    *,
    doctrine: Doctrine,
    crew_ctx: CrewContext,
    capability_profile: dict[str, Any],
    kernel_dag: NamespacedDag,
    validator: Validator,
) -> _RoleBinding:
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
        goal=assemble_goal(spec_module.BASE_GOAL, doctrine),
        backstory=assemble_backstory(spec_module.BASE_BACKSTORY, doctrine),
        tools=list(scoped_tools.values()),
        allow_delegation=False,
        verbose=False,
        llm=None,
    )
    return _RoleBinding(
        name=spec_module.__name__.rsplit(".", 1)[-1],
        agent=agent,
        ctx=ctx,
        tools=scoped_tools,
    )


# ---- Per-doctrine indirect weapon picks --------------------------------------

_INDIRECT_WEAPON_BY_DOCTRINE: dict[Doctrine, str] = {
    "peer": "notional.indirect.medium",
    "near-peer": "notional.indirect.medium",
    "hybrid": "notional.indirect.improvised",
}


# ---- Step functions ----------------------------------------------------------

# A step either commits exactly one event (returns a dict) or — for
# LLM-driven roles — drives one or more tool calls via CrewAI (returns a
# LIST of dicts, one per committed event). The main loop in run_red_crew
# handles both shapes.
_StepResult = Union[dict[str, Any], list[dict[str, Any]]]
_StepFn = Callable[[dict[str, "_RoleBinding"], dict[str, Any]], _StepResult]


def _step_s2_detect(
    roles: dict[str, _RoleBinding], _shared: dict[str, Any]
) -> dict[str, Any]:
    """Use EO_IR modality so detect emits no spatial artifact and the
    validator is skipped — this is the only modality that resolves
    cleanly across all three red profiles (peer / near-peer / hybrid),
    since hybrid lacks `radar_fan` / `ew_cone` / `masint_cell` in its
    effect_parameter_ranges. Classification is omitted entirely from
    the red script: no red profile authorizes `keyhole_footprint`."""
    return roles["s2"].tools["detect"]._run(
        target_entity_id=uuid4(),
        modality="EO_IR",
        confidence=0.80,
        range_m=4_000.0,
    )


def _step_s3_issue_order_to_b(
    roles: dict[str, _RoleBinding], _shared: dict[str, Any]
) -> dict[str, Any]:
    """Peer / near-peer only. Hybrid substitutes _step_s3_send_shadow."""
    return roles["s3"].tools["issue_order"]._run(
        order_type="ATTACK",
        order_payload={
            "objective": "WEST_BANK_OBJECTIVE_AREA",
            "axis_of_advance": "west across crossing",
        },
        to_entity_id=roles["co_b"].ctx.agent_entity_id,
        priority="HIGH",
    )


def _step_s3_request_isr(
    roles: dict[str, _RoleBinding], _shared: dict[str, Any]
) -> dict[str, Any]:
    """Peer / near-peer only."""
    return roles["s3"].tools["request_support"]._run(
        support_type="ISR",
        justification="confirm blue defensive disposition before assault",
        priority="HIGH",
    )


def _step_red_s3_llm_decide(
    roles: dict[str, _RoleBinding], _shared: dict[str, Any]
) -> list[dict[str, Any]]:
    """LLM-driven red S3 (Gemma 4 31B on spark-3fe3, peer/near-peer only).

    The red battalion operations officer reads PyRapide's situation
    report (S2's detect from earlier in this cycle, plus any prior-turn
    events still in the namespace) and decides which orders to issue
    against the Cumberland River crossing objective. Committed events
    cite the situation-report events as causal_predecessors.

    Falls back to the deterministic _step_s3_issue_order_to_b +
    _step_s3_request_isr pair if the LLM call raises.
    """
    s3_role = roles["s3"]

    try:
        llm = build_red_llm()
        results = run_llm_role_step(
            ctx=s3_role.ctx,
            agent=s3_role.agent,
            llm=llm,
            task_description=(
                "You are the red battalion operations officer attempting a "
                "forced crossing of the Cumberland River from the east bank. "
                "Based on the situation report, decide which orders to issue "
                "against the west-bank objective. Use issue_order to direct "
                "Companies A/B/C; use request_support for ISR / fires / EW. "
                "One or two tool calls per turn — keep it tight."
            ),
            expected_output="Tool calls only. No prose.",
        )
        if not results:
            raise RuntimeError("LLM returned no tool calls")
        return [
            {
                "step": f"red.s3.llm_decide.{r.get('verb')}",
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
        s3_role.ctx.causal_predecessors = []
        results = [
            _step_s3_issue_order_to_b(roles, _shared),
            _step_s3_request_isr(roles, _shared),
        ]
        for r in results:
            r["step"] = f"red.s3.llm_decide_fallback.{r['verb']}"
            r["llm_driven"] = False
            r["fallback_reason"] = f"{type(exc).__name__}: {exc}"
        return results


def _step_s3_send_shadow(
    roles: dict[str, _RoleBinding], _shared: dict[str, Any]
) -> dict[str, Any]:
    """Hybrid substitute: S3 (informal) pushes intent over comms."""
    s3_role = roles["s3"]
    # Hybrid S3 has Communicator verbs implicitly via the profile; we
    # construct a synthetic Communicator.send tool bound to s3's ctx
    # for this purpose.
    all_s3_tools = build_all_tools(s3_role.ctx)
    return all_s3_tools["send"]._run(
        channel="VHF",
        message_payload={
            "informal_order": "main effort: cross at center; flanks support",
            "phase": "shape and assault",
        },
        recipient_role="RED_CO_B_INFORMAL",
        priority="IMMEDIATE",
    )


def _step_co_a_assume_posture(
    roles: dict[str, _RoleBinding], _shared: dict[str, Any]
) -> dict[str, Any]:
    # DISMOUNTED is in all three red profiles' allowed_postures
    # (hybrid lacks MOUNTED). Tool doesn't currently profile-check
    # posture but doctrinally we want to stay within the profile's
    # declared set.
    return roles["co_a"].tools["assume_posture"]._run(posture="DISMOUNTED")


def _step_co_a_send_sitrep(
    roles: dict[str, _RoleBinding], _shared: dict[str, Any]
) -> dict[str, Any]:
    return roles["co_a"].tools["send"]._run(
        channel="VHF",
        message_payload={"type": "SITREP", "line1": "in attack position"},
        recipient_role="RED_BN_S3",
        priority="ROUTINE",
    )


def _step_co_b_halt(
    roles: dict[str, _RoleBinding], _shared: dict[str, Any]
) -> dict[str, Any]:
    return roles["co_b"].tools["halt"]._run()


def _step_co_b_engage_with_uncertainty(
    roles: dict[str, _RoleBinding], shared: dict[str, Any]
) -> dict[str, Any]:
    """Co B applies indirect fire on the west-bank objective.

    Uncertainty path: the agent reasons about effective_range_m using the
    profile's posted band, computes the upper-edge "best-case" reach,
    then caps to the profile's effect_parameter_ranges max before
    handing to the validator. Both reasoning_value and committed_value
    are stamped on the step result so the test can assert that band
    reasoning actually occurred.
    """
    profile = shared["profile"]
    weapon_id = shared["indirect_weapon_id"]
    cap = profile["effect_parameter_ranges"]["indirect_fire_arc"]["range_m"]["max"]
    res: UncertaintyResolution = resolve_uncertain_value(
        profile,
        f"effector.weapon_systems[{weapon_id}].effective_range_m",
        profile_cap=cap,
    )
    weapon = next(w for w in profile["effector"]["weapon_systems"] if w["id"] == weapon_id)
    raw = roles["co_b"].tools["engage"]._run(
        target_lat_deg=WEST_BANK_OBJECTIVE_AREA.lat_deg,
        target_lon_deg=WEST_BANK_OBJECTIVE_AREA.lon_deg,
        target_alt_m=WEST_BANK_OBJECTIVE_AREA.alt_m,
        weapon_system=weapon_id,
        volume_count=4,
        intent="NEUTRALIZE",
        range_m=res.chosen,
        time_of_flight_s=float(weapon["time_of_flight_s"]),
        dispersion_ellipse_a_m=80.0,
        dispersion_ellipse_b_m=80.0,
    )
    raw["uncertainty_reasoning"] = {
        "path": f"effector.weapon_systems[{weapon_id}].effective_range_m",
        "nominal": res.nominal,
        "upper_with_band": res.upper_with_band,
        "chosen": res.chosen,
        "capped": res.capped,
        "band_kind": res.band_kind,
        "band_value": res.band_value,
        "profile_cap": cap,
    }
    return raw


def _step_co_c_move(
    roles: dict[str, _RoleBinding], _shared: dict[str, Any]
) -> dict[str, Any]:
    return roles["co_c"].tools["move_to"]._run(
        target_lat_deg=RED_COMPANY_C_POSITION.lat_deg + 0.005,
        target_lon_deg=RED_COMPANY_C_POSITION.lon_deg - 0.002,  # slight westward push
        target_alt_m=RED_COMPANY_C_POSITION.alt_m,
        speed_mps=10.0,
    )


def _step_s6_send_to_higher(
    roles: dict[str, _RoleBinding], _shared: dict[str, Any]
) -> dict[str, Any]:
    return roles["s6"].tools["send"]._run(
        channel="VHF",
        message_payload={"type": "comms-status", "status": "green"},
        recipient_role="RED_BRIGADE_S6",
        priority="ROUTINE",
    )


def _step_s6_report(
    roles: dict[str, _RoleBinding], _shared: dict[str, Any]
) -> dict[str, Any]:
    return roles["s6"].tools["report"]._run(
        report_type="SITREP",
        report_payload={
            "comms": "nominal",
            "blue_jamming_observed": False,
            "channels_in_use": ["VHF"],
        },
        to_echelon="BRIGADE",
    )


# ---- Per-doctrine script assembly --------------------------------------------


def _build_script(doctrine: Doctrine) -> list[tuple[str, _StepFn]]:
    """Assemble the deterministic step list per doctrine.

    Peer / near-peer: 11 steps including S3 issue_order + request_support.
    Hybrid: 10 steps (S3 issue_order replaced by send_shadow; no
    request_support).
    """
    common_prefix = [
        ("s2.detect", _step_s2_detect),
    ]
    if doctrine == "hybrid":
        # Hybrid lacks Commander verbs; S3 falls back to a Communicator
        # send. LLM-driven flow doesn't apply here.
        s3_steps: list[tuple[str, _StepFn]] = [
            ("s3.send_shadow", _step_s3_send_shadow),
        ]
    else:
        # Peer / near-peer: S3 is LLM-driven (Gemma 4 31B on spark-3fe3).
        # The single entry expands to 1-2 events at runtime depending on
        # the LLM's tool calls; in fallback mode it expands to exactly 2.
        s3_steps = [
            ("red.s3.llm_decide", _step_red_s3_llm_decide),
        ]
    common_suffix = [
        ("co_a.assume_posture", _step_co_a_assume_posture),
        ("co_a.send", _step_co_a_send_sitrep),
        ("co_b.halt", _step_co_b_halt),
        ("co_b.engage", _step_co_b_engage_with_uncertainty),
        ("co_c.move_to", _step_co_c_move),
        ("s6.send", _step_s6_send_to_higher),
        ("s6.report", _step_s6_report),
    ]
    return common_prefix + s3_steps + common_suffix


# ---- Public entry point ------------------------------------------------------


def run_red_crew(
    crew_ctx: CrewContext,
    doctrine: Doctrine | None = None,
) -> CrewResult:
    """Execute one between-turn cycle for the red OpFor crew.

    Args:
        crew_ctx: tenant / scenario / turn from the harness.
        doctrine: explicit doctrine flavor; if None, resolves via
            ``ALMIGHTY_RED_DOCTRINE`` env var, falling back to ``"peer"``.

    Returns a :class:`CrewResult` with per-step outcomes in metadata,
    including the uncertainty reasoning recorded on the engage step.
    """
    started = time.perf_counter()
    resolved_doctrine = select_doctrine(doctrine)
    profile = load_profile(resolved_doctrine)
    kernel_dag = NamespacedDag()
    validator = Validator()

    bindings = {
        m.__name__.rsplit(".", 1)[-1]: _build_role(
            m,
            doctrine=resolved_doctrine,
            crew_ctx=crew_ctx,
            capability_profile=profile,
            kernel_dag=kernel_dag,
            validator=validator,
        )
        for m in _ROLE_MODULES
    }
    shared: dict[str, Any] = {
        "doctrine": resolved_doctrine,
        "profile": profile,
        "indirect_weapon_id": _INDIRECT_WEAPON_BY_DOCTRINE[resolved_doctrine],
    }
    script = _build_script(resolved_doctrine)
    step_outcomes: list[dict[str, Any]] = []
    for label, step_fn in script:
        result = step_fn(bindings, shared)
        if isinstance(result, list):
            # LLM-driven step returns one entry per committed event; the
            # entries already have their own "step" labels.
            step_outcomes.extend(result)
        else:
            step_outcomes.append({"step": label, **result})

    duration_ms = int((time.perf_counter() - started) * 1000)
    return CrewResult(
        crew="red",
        duration_ms=duration_ms,
        notes=(
            f"v1 deterministic red crew — doctrine={resolved_doctrine}; "
            f"{len(step_outcomes)} events committed"
        ),
        metadata={
            "tenant_id": crew_ctx.tenant_id,
            "scenario_id": crew_ctx.scenario_id,
            "turn": crew_ctx.turn,
            "doctrine": resolved_doctrine,
            "profile_id": profile.get("profile_id"),
            "events_committed": len(step_outcomes),
            "steps": step_outcomes,
            "validator_rejections": 0,
            "indirect_weapon_id": shared["indirect_weapon_id"],
        },
    )


# Convenience export for the eventual WS-401 integration. The harness's
# RED_CREWS["default"] swap should land alongside BLUE_RUNNER + the
# WS-405 white-cell runner so all three crews go live together.
RED_RUNNER: Callable[[CrewContext], CrewResult] = run_red_crew
