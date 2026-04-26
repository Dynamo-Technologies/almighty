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

from .llm_clients import LLMConfig

if TYPE_CHECKING:
    from crewai import Agent
    from almighty_officer_tools.context import OfficerToolContext


# Default per-call timeout. Demo overrides via ALMIGHTY_LLM_TIMEOUT_S.
_DEFAULT_TIMEOUT_S = 60.0


def run_llm_role_step(
    *,
    ctx: "OfficerToolContext",
    agent: "Agent",
    llm: LLMConfig,
    task_description: str,
    expected_output: str,
) -> list[dict[str, Any]]:
    """Run one LLM-driven role step. Returns the list of tool-result
    dicts from each tool call the LLM emitted. Each dict has the shape
    OfficerToolBase._run produces (event_id, verb, officer_type,
    validator, causal_predecessors).

    The dicts are the source of truth for the wire format the FastAPI
    shim relays back — do NOT rely on dag.read() for predecessors,
    because the kernel's _reconstruct drops causal_predecessors by
    design (see kernel/almighty_kernel/dag.py:243).

    Side effects: mutates ctx.causal_predecessors twice (set then reset)
    and commits one KernelEvent per tool call to ctx.kernel_dag.
    """
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
        timeout = float(os.environ.get("ALMIGHTY_LLM_TIMEOUT_S", _DEFAULT_TIMEOUT_S))
        messages = [
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
        ]

        # 4. Provider dispatch. Both branches return an OpenAI-shaped
        #    completion so the rest of the pipeline doesn't care which
        #    backend served it.
        if llm.provider == "bedrock":
            completion = _call_bedrock(llm=llm, messages=messages, tools=tool_specs)
        else:
            completion = _call_chat_completions(
                llm=llm, messages=messages, tools=tool_specs, timeout=timeout,
            )

        # 5. Run any tool calls the model emitted; collect their result dicts.
        return _run_tool_calls(agent.tools, completion)
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
    llm: LLMConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    timeout: float,
) -> dict[str, Any]:
    """Direct call to /v1/chat/completions on the LLM's base_url (vllm path)."""
    base_url = (llm.base_url or "").rstrip("/")
    if not base_url:
        raise RuntimeError("LLM has no base_url; nothing to call")
    # vLLM strips the provider prefix from the served name; use whatever
    # the model field carries.
    model = llm.model or ""
    api_key = llm.api_key or "EMPTY"
    body = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": float(llm.temperature),
    }
    resp = httpx.post(
        f"{base_url}/chat/completions",
        json=body,
        headers={"authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def _call_bedrock(
    *,
    llm: LLMConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    """Bedrock Converse API call. Translates OpenAI-shape messages/tools
    into the Bedrock shape, invokes converse, then translates the
    response back to the OpenAI shape so _run_tool_calls is unchanged.

    boto3 picks up creds from the EC2 instance-metadata service; the
    instance role needs bedrock:InvokeModel on the target model arn.
    """
    import boto3  # imported lazily so vllm-only deployments don't need boto3

    if not llm.model_id:
        raise RuntimeError("Bedrock LLM has no model_id")
    client = boto3.client("bedrock-runtime", region_name=llm.region or "us-east-1")

    # Translate messages: pull `system` out into the top-level system
    # block; everything else into Bedrock's role/content shape.
    system_blocks = []
    bedrock_messages = []
    for m in messages:
        if m.get("role") == "system":
            system_blocks.append({"text": m.get("content", "")})
        else:
            bedrock_messages.append({
                "role": m["role"],
                "content": [{"text": m.get("content", "") or ""}],
            })

    # Translate tool specs: OpenAI's {type:function, function:{name,description,parameters}}
    # → Bedrock's {toolSpec:{name,description,inputSchema:{json:…}}}
    bedrock_tools = []
    for t in tools:
        fn = t.get("function") or {}
        bedrock_tools.append({
            "toolSpec": {
                "name": fn.get("name", "tool"),
                "description": fn.get("description", ""),
                "inputSchema": {"json": fn.get("parameters") or {"type": "object", "properties": {}}},
            },
        })

    response = client.converse(
        modelId=llm.model_id,
        messages=bedrock_messages,
        system=system_blocks,
        toolConfig={
            "tools": bedrock_tools,
            "toolChoice": {"auto": {}},
        },
        inferenceConfig={
            "temperature": float(llm.temperature),
            "maxTokens": 1024,
        },
    )

    # Translate Bedrock response → OpenAI completion shape so the rest
    # of llm_step doesn't care which backend was used.
    msg = ((response.get("output") or {}).get("message") or {})
    contents = msg.get("content") or []
    tool_calls = []
    text_parts = []
    for block in contents:
        if "toolUse" in block:
            tu = block["toolUse"]
            tool_calls.append({
                "id": tu.get("toolUseId", ""),
                "type": "function",
                "function": {
                    "name": tu.get("name", ""),
                    "arguments": json.dumps(tu.get("input") or {}),
                },
            })
        elif "text" in block:
            text_parts.append(block["text"])

    finish = "tool_calls" if tool_calls else "stop"
    return {
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "\n".join(text_parts) if text_parts else None,
                "tool_calls": tool_calls,
            },
            "finish_reason": finish,
        }],
    }


def _run_tool_calls(tools: list, completion: dict[str, Any]) -> list[dict[str, Any]]:
    """Look up each tool_call by name and invoke its _run(**args).
    Returns the list of result dicts (in tool_calls order). Tool calls
    that can't be parsed or don't match a bound tool are skipped silently."""
    choices = completion.get("choices") or []
    if not choices:
        return []
    message = choices[0].get("message") or {}
    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        return []  # Model responded with text only — caller's fallback will run

    by_name = {getattr(t, "name", type(t).__name__): t for t in tools}
    results: list[dict[str, Any]] = []
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
        result = tool._run(**args)
        if isinstance(result, dict):
            results.append(result)
    return results
