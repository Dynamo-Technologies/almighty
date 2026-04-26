"""Tests for build_situation_report and predecessor_event_ids.

Spec §6a — PyRapide → agent half of the demo edit. The LLM-driven role
gets a topologically-ordered text view of the events in its scenario
namespace; the same call also returns the event ids so the next commit
auto-links them as parents.
"""

from __future__ import annotations

from uuid import uuid4

from almighty_kernel.dag import KernelEvent, NamespacedDag

from almighty_agent_runtime.situation_report import (
    build_situation_report,
    predecessor_event_ids,
)


def _commit(dag: NamespacedDag, tenant_id, scenario_id, *, verb, payload, predecessors=None):
    e = KernelEvent(
        event_id=uuid4(),
        tenant_id=tenant_id,
        scenario_id=scenario_id,
        turn=1,
        source_officer_type="SENSOR",
        source_entity_id=uuid4(),
        action_verb=verb,
        payload=payload,
        causal_predecessors=predecessors or [],
    )
    dag.commit(e)
    return e


def test_situation_report_lists_events_in_topological_order():
    tenant_id = uuid4()
    scenario_id = uuid4()
    dag = NamespacedDag()

    e1 = _commit(
        dag, tenant_id, scenario_id,
        verb="detect",
        payload={"target_entity_id": str(uuid4()), "modality": "RADAR", "confidence": 0.85},
    )
    e2 = _commit(
        dag, tenant_id, scenario_id,
        verb="classify",
        payload={"track_id": str(uuid4()), "classification_label": "uas.medium", "confidence": 0.78},
        predecessors=[e1.event_id],
    )

    report = build_situation_report(dag, tenant_id=tenant_id, scenario_id=scenario_id)
    assert "detect" in report
    assert "classify" in report
    assert report.index("detect") < report.index("classify")
    assert str(e1.event_id) in report
    assert str(e2.event_id) in report


def test_situation_report_empty_namespace_returns_empty_string():
    dag = NamespacedDag()
    report = build_situation_report(dag, tenant_id=uuid4(), scenario_id=uuid4())
    assert report == ""


def test_predecessor_event_ids_returns_topological_uuids():
    tenant_id = uuid4()
    scenario_id = uuid4()
    dag = NamespacedDag()
    e1 = _commit(dag, tenant_id, scenario_id, verb="detect", payload={})
    e2 = _commit(dag, tenant_id, scenario_id, verb="classify", payload={}, predecessors=[e1.event_id])

    parents = predecessor_event_ids(dag, tenant_id=tenant_id, scenario_id=scenario_id)
    assert parents == [e1.event_id, e2.event_id]


def test_predecessor_event_ids_empty_namespace():
    dag = NamespacedDag()
    parents = predecessor_event_ids(dag, tenant_id=uuid4(), scenario_id=uuid4())
    assert parents == []
