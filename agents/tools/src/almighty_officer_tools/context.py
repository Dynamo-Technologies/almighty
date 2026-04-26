"""OfficerToolContext + ToolError.

Each tool instance is bound to one (agent, capability_profile, scenario)
context at construction time. The runtime parameters that change per
tool call (verb-specific args) are passed to ``_run`` as keyword args.

This is the contract WS-403 / WS-404 / WS-405 will produce a context
for when they instantiate per-agent tool sets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from almighty_czml_validator import Validator
from almighty_kernel.dag import NamespacedDag


class ToolError(RuntimeError):
    """Raised when a tool call cannot proceed.

    Distinct exception type so CrewAI agent loops can recognize tool-side
    rejection (capability gate or validator reject) as distinct from a
    raw library exception.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class OfficerToolContext:
    """Inputs every officer tool receives at construction.

    The fields below MUST be supplied by whoever instantiates the tool
    (in v1, the test harness; in WS-403/404/405, the crew that wires
    agents to tools).
    """

    tenant_id: UUID
    scenario_id: UUID
    turn: int
    agent_entity_id: UUID
    capability_profile: dict[str, Any]
    kernel_dag: NamespacedDag
    validator: Validator
    # The role's prepare-step (e.g., run_llm_role_step in the agent runtime)
    # populates this with event ids the LLM saw in its situation report;
    # OfficerToolBase._run reads it on commit so the new event chains back
    # to those parents. Spec §6b. Empty list (default) preserves the
    # existing v1 deterministic behavior.
    causal_predecessors: list[UUID] = field(default_factory=list)
