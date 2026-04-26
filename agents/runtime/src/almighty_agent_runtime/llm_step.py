"""Run a single LLM-driven role step.

Spec §6 — the helper that ties PyRapide-as-input to
causal-predecessors-on-output. The role's CrewAI Agent is already
configured with tools (the role's allowed verbs are bound in
`_build_role` in each crew). This helper:

  1. Builds the situation report from the namespaced DAG.
  2. Stashes the situation report's event ids on the context's
     `causal_predecessors` field — `OfficerToolBase._run` reads from there
     when it commits the event.
  3. Constructs a single-task Crew, attaches the LLM, and calls `kickoff()`.
  4. Resets the context's predecessors to [] so the next deterministic
     step in the cycle isn't accidentally linked.

The caller decides what to do if the LLM call raises (typically: fall
back to deterministic behavior — see the crew's wrapper in
agents/blue/.../crew.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from crewai import Crew, Task

from .situation_report import build_situation_report, predecessor_event_ids

if TYPE_CHECKING:
    from crewai import LLM, Agent

    from almighty_officer_tools.context import OfficerToolContext


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
    via the configured kernel_dag during kickoff."""

    # 1. Build the situation report and capture its event ids.
    report = build_situation_report(
        ctx.kernel_dag, tenant_id=ctx.tenant_id, scenario_id=ctx.scenario_id,
    )
    parents = predecessor_event_ids(
        ctx.kernel_dag, tenant_id=ctx.tenant_id, scenario_id=ctx.scenario_id,
    )

    # 2. Stash predecessors so the tool commit auto-links.
    ctx.causal_predecessors = parents

    # 3. Build and run the crew.
    agent.llm = llm  # late-binding so tests can pass a mock and so the
                    # v1 crews (constructed with llm=None) get bound here
    task = Task(
        description=(
            task_description
            + "\n\nSituation report (causal-order events from PyRapide):\n"
            + (report or "(no prior events)")
        ),
        expected_output=expected_output,
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], verbose=False)
    crew.kickoff()

    # 4. Reset for the next deterministic step.
    ctx.causal_predecessors = []
