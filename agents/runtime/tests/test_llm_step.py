"""Tests for run_llm_role_step.

Spec §6 — the helper that ties PyRapide-as-input to predecessors-on-output.
The implementation does a direct OpenAI-compatible call to vLLM rather
than going through CrewAI's agent loop (rationale documented in
llm_step.py). Tests mock httpx.post so we don't actually hit a vLLM.
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
        capability_profile={"action_verbs_available": ["issue_order"]},
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


def _mock_llm():
    llm = MagicMock(name="llm")
    llm.base_url = "http://stub:9000/v1"
    llm.model = "stub-model"
    llm.api_key = "EMPTY"
    llm.temperature = 0.3
    return llm


def _mock_tool(name: str = "issue_order"):
    """A stub tool that mirrors what OfficerToolBase exposes."""
    tool = MagicMock(name=f"tool-{name}")
    tool.name = name
    tool.description = f"Stub for {name}"
    tool.args_schema = None  # falls back to {"type":"object","properties":{}}
    return tool


def _mock_agent(tools):
    agent = MagicMock(name="agent")
    agent.tools = tools
    agent.role = "S3"
    agent.goal = "decide"
    agent.backstory = "the operations officer"
    return agent


def _vllm_response_with_tool_call(*, name="issue_order", args=None):
    """Minimal OpenAI-format response shape with a tool_call."""
    import json as _json
    return MagicMock(
        status_code=200,
        json=MagicMock(return_value={
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "tc-1",
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": _json.dumps(args or {"order_type": "MOVE"}),
                        },
                    }],
                },
                "finish_reason": "tool_calls",
            }],
        }),
        raise_for_status=MagicMock(),
    )


def test_run_llm_role_step_sets_predecessors_before_tool_call_and_resets_after():
    dag = NamespacedDag()
    ctx = _make_ctx(dag)
    e1 = _seed(dag, ctx, verb="detect")
    e2 = _seed(dag, ctx, verb="classify")

    captured_predecessors: list[list] = []
    tool = _mock_tool("issue_order")

    def tool_run(**kwargs):
        captured_predecessors.append(list(ctx.causal_predecessors))
        return {"event_id": "x", "verb": "issue_order"}

    tool._run = MagicMock(side_effect=tool_run)
    agent = _mock_agent([tool])
    llm = _mock_llm()

    with patch("almighty_agent_runtime.llm_step.httpx.post") as mock_post:
        mock_post.return_value = _vllm_response_with_tool_call(name="issue_order")
        run_llm_role_step(
            ctx=ctx, agent=agent, llm=llm,
            task_description="Decide.",
            expected_output="Tool calls only.",
        )

    # Predecessors visible to tool._run were exactly the seeded events.
    assert captured_predecessors == [[e1.event_id, e2.event_id]]
    # And reset to empty afterward.
    assert ctx.causal_predecessors == []
    # The tool was called once with the LLM-supplied args.
    tool._run.assert_called_once_with(order_type="MOVE")


def test_run_llm_role_step_includes_situation_report_in_user_message():
    dag = NamespacedDag()
    ctx = _make_ctx(dag)
    _seed(dag, ctx, verb="detect")

    tool = _mock_tool("issue_order")
    tool._run = MagicMock(return_value={"event_id": "x"})
    agent = _mock_agent([tool])
    llm = _mock_llm()

    with patch("almighty_agent_runtime.llm_step.httpx.post") as mock_post:
        mock_post.return_value = _vllm_response_with_tool_call()
        run_llm_role_step(
            ctx=ctx, agent=agent, llm=llm,
            task_description="Decide what to do.",
            expected_output="Tool calls only.",
        )

    body = mock_post.call_args.kwargs["json"]
    user_msg = next(m for m in body["messages"] if m["role"] == "user")
    assert "Decide what to do." in user_msg["content"]
    assert "detect" in user_msg["content"]
    assert "Tool calls only." in user_msg["content"]


def test_run_llm_role_step_handles_text_only_response():
    """If Gemma replies with text (no tool_calls), the step doesn't error;
    the caller's fallback will then handle the empty-event case."""
    dag = NamespacedDag()
    ctx = _make_ctx(dag)

    tool = _mock_tool("issue_order")
    tool._run = MagicMock()
    agent = _mock_agent([tool])
    llm = _mock_llm()

    text_only = MagicMock(
        status_code=200,
        json=MagicMock(return_value={
            "choices": [{
                "message": {"role": "assistant", "content": "I won't call a tool."},
                "finish_reason": "stop",
            }],
        }),
        raise_for_status=MagicMock(),
    )
    with patch("almighty_agent_runtime.llm_step.httpx.post") as mock_post:
        mock_post.return_value = text_only
        run_llm_role_step(
            ctx=ctx, agent=agent, llm=llm,
            task_description="x", expected_output="y",
        )

    tool._run.assert_not_called()
    assert ctx.causal_predecessors == []


def test_run_llm_role_step_resets_predecessors_on_exception():
    """If httpx raises (e.g., timeout), ctx.causal_predecessors must still
    be reset so the next deterministic step doesn't link to the wrong parents."""
    dag = NamespacedDag()
    ctx = _make_ctx(dag)
    _seed(dag, ctx, verb="detect")

    agent = _mock_agent([_mock_tool("issue_order")])
    llm = _mock_llm()

    with patch("almighty_agent_runtime.llm_step.httpx.post") as mock_post:
        mock_post.side_effect = httpx_TimeoutError = RuntimeError("simulated timeout")
        try:
            run_llm_role_step(
                ctx=ctx, agent=agent, llm=llm,
                task_description="x", expected_output="y",
            )
        except RuntimeError:
            pass

    assert ctx.causal_predecessors == []
