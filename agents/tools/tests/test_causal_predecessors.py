"""Tests for OfficerToolContext.causal_predecessors field shape.

Spec §6b — load-bearing field on the context. The role's prepare-step
populates it; OfficerToolBase._run uses it when committing the event.
The base.py integration is covered separately in
test_predecessors_on_commit.py (Task 3.2).
"""

from __future__ import annotations

from uuid import uuid4

from almighty_czml_validator import Validator
from almighty_kernel.dag import NamespacedDag

from almighty_officer_tools.context import OfficerToolContext


def _ctx_minimal(*, predecessors=None) -> OfficerToolContext:
    kwargs: dict = dict(
        tenant_id=uuid4(),
        scenario_id=uuid4(),
        turn=1,
        agent_entity_id=uuid4(),
        capability_profile={"action_verbs_available": []},
        kernel_dag=NamespacedDag(),
        validator=Validator(),
    )
    if predecessors is not None:
        kwargs["causal_predecessors"] = predecessors
    return OfficerToolContext(**kwargs)


def test_context_default_predecessors_is_empty_list():
    ctx = _ctx_minimal()
    assert ctx.causal_predecessors == []


def test_context_carries_caller_supplied_predecessors():
    pid = uuid4()
    ctx = _ctx_minimal(predecessors=[pid])
    assert ctx.causal_predecessors == [pid]
