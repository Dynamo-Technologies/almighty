"""Run a single LLM-driven role step.

Spec §6 — the helper that ties PyRapide-as-input to
causal-predecessors-on-output.

Implementation note (2026-04-26): we bypass CrewAI's agent loop and
make a direct OpenAI-compatible call to vLLM. CrewAI's `Crew.kickoff()`
+ `hosted_vllm/...` provider has an issue where it doesn't recognize
correctly-formatted tool_calls responses (vLLM returns OpenAI-perfect
tool calls, but CrewAI's loop re-prompts in a tight retry — observed
~25 retries over 80s before quitting). For our use case (one task,
one tool call, one event committed) the agent-loop ceremony adds
nothing; a single chat-completions request is enough.

The flow:

  1. Build situation report from kernel_dag.read(causal_order=True).
  2. Stash the report's event ids on ctx.causal_predecessors —
     OfficerToolBase._run reads them on commit.
  3. Build OpenAI-format tool specs from the agent's bound tools.
  4. POST /v1/chat/completions with the system + user messages and
     tool_choice='auto'. Bound by httpx timeout so a hang is fast.
  5. Parse tool_calls[0], look up the corresponding tool by name,
     and call its _run(**args). The tool itself commits the
     KernelEvent with the predecessors set on the context.
  6. Reset ctx.causal_predecessors to [] so the next deterministic
     step in the cycle isn't accidentally linked.

The caller (the crew's _step_*_llm_decide) handles failures: any
exception here propagates and the crew falls back to the deterministic
script with a logged fallback_reason. This is the demo's safety net.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx

from .situation_report import build_situation_report, predecessor_event_ids

if TYPE_CHECKING:
    from crewai import LLM, Agent
    from almighty_officer_tools.context import OfficerToolContext


# Default per-call timeout. Demo overrides via ALMIGHTY_LLM_TIMEOUT_S.
_DEFAULT_TIMEOUT_S = 60.0


def run_llm_role_step(
    *,
    ctx: "OfficerToolContext",
    agent: "Agent",
    llm: "LLM",
    task_description: str,
    expected_output: str,
) -> None:
    """Run one LLM-driven role step. Mutates ctx.causal_predecessors twice
    (set then reset). Side-effect: the agent's tools commit a KernelEvent
    via the configured kernel_dag during this call."""
    import os

    # 1. Situation report + predecessors capture.
    report = build_situation_report(
        ctx.kernel_dag, tenant_id=ctx.tenant_id, scenario_id=ctx.scenario_id,
    )
    parents = predecessor_event_ids(
        ctx.kernel_dag, tenant_id=ctx.tenant_id, scenario_id=ctx.scenario_id,
    )

    # 2. Stash predecessors so the tool commit auto-links.
    ctx.causal_predecessors = parents

    try:
        # 3. Build OpenAI-format tool specs from the agent's bound tools.
        tool_specs = _build_tool_specs(agent.tools)

        # 4. Direct chat-completions call.
        completion = _call_chat_completions(
            llm=llm,
            messages=[
                {
                    "role": "system",
                    "content": _system_prompt(agent),
                },
                {
                    "role": "user",
                    "content": (
                        task_description
                        + "\n\nSituation report (causal-order events from PyRapide):\n"
                        + (report or "(no prior events)")
                        + "\n\nExpected output: " + expected_output
                    ),
                },
            ],
            tools=tool_specs,
            timeout=float(os.environ.get("ALMIGHTY_LLM_TIMEOUT_S", _DEFAULT_TIMEOUT_S)),
        )

        # 5. Run any tool calls the model emitted.
        _run_tool_calls(agent.tools, completion)
    finally:
        # 6. Reset for the next deterministic step (defense-in-depth).
        ctx.causal_predecessors = []


def _system_prompt(agent: "Agent") -> str:
    role = getattr(agent, "role", "") or ""
    goal = getattr(agent, "goal", "") or ""
    backstory = getattr(agent, "backstory", "") or ""
    return f"You are: {role}\n\nGoal: {goal}\n\nBackground: {backstory}"


def _build_tool_specs(tools: list) -> list[dict[str, Any]]:
    """Convert each CrewAI tool into the OpenAI /chat/completions tool spec."""
    specs: list[dict[str, Any]] = []
    for tool in tools:
        name = getattr(tool, "name", None) or type(tool).__name__
        description = getattr(tool, "description", "") or ""
        schema_cls = getattr(tool, "args_schema", None)
        if schema_cls is not None and hasattr(schema_cls, "model_json_schema"):
            params = schema_cls.model_json_schema()
            # OpenAI's tool-spec format expects 'parameters' to be a JSON-Schema
            # object — strip top-level 'title' which OpenAI/litellm sometimes complains about.
            params.pop("title", None)
        else:
            params = {"type": "object", "properties": {}}
        specs.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": params,
            },
        })
    return specs


def _call_chat_completions(
    *,
    llm: "LLM",
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    timeout: float,
) -> dict[str, Any]:
    """Direct call to /v1/chat/completions on the LLM's base_url."""
    base_url = (getattr(llm, "base_url", "") or "").rstrip("/")
    if not base_url:
        raise RuntimeError("LLM has no base_url; nothing to call")
    # llm.model can come back with the provider prefix stripped (e.g.
    # "google/gemma-4-26B-A4B-it" rather than "hosted_vllm/google/...").
    # Use it raw — vLLM expects the served-as name.
    model = getattr(llm, "model", "")
    api_key = getattr(llm, "api_key", "EMPTY") or "EMPTY"
    body = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": float(getattr(llm, "temperature", 0.3) or 0.3),
    }
    resp = httpx.post(
        f"{base_url}/chat/completions",
        json=body,
        headers={"authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def _run_tool_calls(tools: list, completion: dict[str, Any]) -> None:
    """Look up each tool_call by name and invoke its _run(**args)."""
    choices = completion.get("choices") or []
    if not choices:
        return
    message = choices[0].get("message") or {}
    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        return  # Model responded with text only — caller's fallback will run

    by_name = {getattr(t, "name", type(t).__name__): t for t in tools}
    for tc in tool_calls:
        fn = (tc or {}).get("function") or {}
        name = fn.get("name")
        args_str = fn.get("arguments") or "{}"
        try:
            args = json.loads(args_str) if isinstance(args_str, str) else (args_str or {})
        except json.JSONDecodeError:
            continue
        tool = by_name.get(name)
        if tool is None:
            continue
        tool._run(**args)
