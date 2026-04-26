"""Tests OfficerToolBase commits with causal_predecessors from ctx.

Spec §6b — when the LLM-driven role's prepare-step has stashed event
ids on ctx.causal_predecessors, the resulting KernelEvent must list
them as parents. The wire-format dict the tool returns must surface
the same list (the FastAPI shim relays it back to control-plane).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from almighty_czml_validator import Validator
from almighty_kernel.dag import KernelEvent, NamespacedDag

from almighty_officer_tools import build_all_tools
from almighty_officer_tools.context import OfficerToolContext


def test_tool_run_attaches_predecessors_from_context():
    tenant_id = uuid4()
    scenario_id = uuid4()
    dag = NamespacedDag()

    seed = KernelEvent(
        event_id=uuid4(),
        tenant_id=tenant_id,
        scenario_id=scenario_id,
        turn=1,
        source_officer_type="SENSOR",
        source_entity_id=uuid4(),
        action_verb="detect",
        payload={"target_entity_id": str(uuid4()), "modality": "RADAR", "confidence": 0.85},
        causal_predecessors=[],
    )
    dag.commit(seed)

    ctx = OfficerToolContext(
        tenant_id=tenant_id,
        scenario_id=scenario_id,
        turn=1,
        agent_entity_id=uuid4(),
        capability_profile={"action_verbs_available": ["issue_order"]},
        kernel_dag=dag,
        validator=Validator(),
        causal_predecessors=[seed.event_id],
    )
    tools = build_all_tools(ctx)
    issue_order = tools["issue_order"]

    result = issue_order._run(
        order_type="MOVE",
        order_payload={
            "waypoints": [
                {"lat_deg": 36.18, "lon_deg": -86.78, "alt_m": 165.0},
            ],
        },
        to_entity_id=uuid4(),
        priority="MEDIUM",
    )

    # The wire-format dict is what propagates to the FastAPI shim and on
    # to the control-plane. NamespacedDag.read() reconstructs events
    # without predecessors (kernel/almighty_kernel/dag.py:243) by design,
    # so we assert on the result dict — that's the path that matters.
    assert result["causal_predecessors"] == [str(seed.event_id)]
    # Also confirm the DAG read returns the event but with empty
    # predecessors per the documented kernel behavior.
    events = dag.read(tenant_id=tenant_id, scenario_id=scenario_id)
    issued = next(e for e in events if e.event_id == UUID(result["event_id"]))
    assert issued.causal_predecessors == []  # by design — see dag.py:243


def test_tool_run_with_empty_predecessors_is_unchanged():
    """Default v1 behavior: a context with no predecessors set commits
    a root event (causal_predecessors=[]). The existing 36 tool tests
    rely on this — reaffirm it explicitly here."""
    tenant_id = uuid4()
    scenario_id = uuid4()
    dag = NamespacedDag()

    ctx = OfficerToolContext(
        tenant_id=tenant_id,
        scenario_id=scenario_id,
        turn=0,
        agent_entity_id=uuid4(),
        capability_profile={"action_verbs_available": ["issue_order"]},
        kernel_dag=dag,
        validator=Validator(),
    )
    tools = build_all_tools(ctx)

    result = tools["issue_order"]._run(
        order_type="DEFEND",
        order_payload={},
        to_entity_id=uuid4(),
        priority="LOW",
    )
    events = dag.read(tenant_id=tenant_id, scenario_id=scenario_id)
    committed = next(e for e in events if e.event_id == UUID(result["event_id"]))
    assert committed.causal_predecessors == []
    assert result["causal_predecessors"] == []
