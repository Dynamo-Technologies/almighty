"""Tests for run_llm_role_step.

Spec §6 — the helper that ties PyRapide-as-input to causal-predecessors-on-output.
Mocks crewai.Crew + Task so we don't make real LLM calls in CI.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

from almighty_czml_validator import Validator
from almighty_kernel.dag import KernelEvent, NamespacedDag
from almighty_officer_tools.context import OfficerToolContext

from almighty_agent_runtime.llm_step import run_llm_role_step


def _make_ctx(dag: NamespacedDag) -> OfficerToolContext:
    return OfficerToolContext(
        tenant_id=uuid4(),
        scenario_id=uuid4(),
        turn=1,
        agent_entity_id=uuid4(),
        capability_profile={"action_verbs_available": ["issue_order", "request_support"]},
        kernel_dag=dag,
        validator=Validator(),
    )


def _seed(dag: NamespacedDag, ctx: OfficerToolContext, *, verb: str) -> KernelEvent:
    e = KernelEvent(
        event_id=uuid4(),
        tenant_id=ctx.tenant_id,
        scenario_id=ctx.scenario_id,
        turn=1,
        source_officer_type="SENSOR",
        source_entity_id=uuid4(),
        action_verb=verb,
        payload={},
        causal_predecessors=[],
    )
    dag.commit(e)
    return e


def test_run_llm_role_step_sets_predecessors_before_kickoff():
    dag = NamespacedDag()
    ctx = _make_ctx(dag)
    e1 = _seed(dag, ctx, verb="detect")
    e2 = _seed(dag, ctx, verb="classify")

    fake_agent = MagicMock(name="agent")
    fake_llm = MagicMock(name="llm")

    captured_predecessors: list[list] = []

    with patch("almighty_agent_runtime.llm_step.Crew") as MockCrew, \
         patch("almighty_agent_runtime.llm_step.Task"):
        # Capture ctx.causal_predecessors at the moment kickoff is called
        def kickoff_side_effect():
            captured_predecessors.append(list(ctx.causal_predecessors))
            return MagicMock(raw="(unused)")
        MockCrew.return_value.kickoff = MagicMock(side_effect=kickoff_side_effect)

        run_llm_role_step(
            ctx=ctx,
            agent=fake_agent,
            llm=fake_llm,
            task_description="Decide.",
            expected_output="Tool calls.",
        )

    assert captured_predecessors == [[e1.event_id, e2.event_id]]


def test_run_llm_role_step_resets_predecessors_after():
    """Defense-in-depth: leaving predecessors set across roles would link
    later deterministic events to the wrong parents."""
    dag = NamespacedDag()
    ctx = _make_ctx(dag)
    _seed(dag, ctx, verb="detect")
    fake_agent = MagicMock()
    fake_llm = MagicMock()

    with patch("almighty_agent_runtime.llm_step.Crew") as MockCrew, \
         patch("almighty_agent_runtime.llm_step.Task"):
        MockCrew.return_value.kickoff = MagicMock(return_value=MagicMock(raw="x"))
        run_llm_role_step(
            ctx=ctx, agent=fake_agent, llm=fake_llm,
            task_description="x", expected_output="x",
        )

    assert ctx.causal_predecessors == []


def test_run_llm_role_step_attaches_llm_to_agent():
    """The agent is constructed with llm=None (deterministic v1). The
    helper must attach the supplied LLM to the agent before kickoff."""
    dag = NamespacedDag()
    ctx = _make_ctx(dag)
    fake_agent = MagicMock(name="agent")
    fake_llm = MagicMock(name="llm")

    with patch("almighty_agent_runtime.llm_step.Crew") as MockCrew, \
         patch("almighty_agent_runtime.llm_step.Task"):
        MockCrew.return_value.kickoff = MagicMock(return_value=MagicMock(raw="x"))
        run_llm_role_step(
            ctx=ctx, agent=fake_agent, llm=fake_llm,
            task_description="x", expected_output="x",
        )

    assert fake_agent.llm == fake_llm


def test_run_llm_role_step_includes_situation_report_in_task_description():
    dag = NamespacedDag()
    ctx = _make_ctx(dag)
    _seed(dag, ctx, verb="detect")

    fake_agent = MagicMock()
    fake_llm = MagicMock()
    captured_descriptions = []

    with patch("almighty_agent_runtime.llm_step.Crew") as MockCrew, \
         patch("almighty_agent_runtime.llm_step.Task") as MockTask:
        MockTask.side_effect = lambda **kwargs: captured_descriptions.append(kwargs["description"]) or MagicMock()
        MockCrew.return_value.kickoff = MagicMock(return_value=MagicMock(raw="x"))
        run_llm_role_step(
            ctx=ctx, agent=fake_agent, llm=fake_llm,
            task_description="Decide what to do.",
            expected_output="x",
        )

    assert len(captured_descriptions) == 1
    assert "Decide what to do." in captured_descriptions[0]
    # Situation report is embedded
    assert "detect" in captured_descriptions[0]
