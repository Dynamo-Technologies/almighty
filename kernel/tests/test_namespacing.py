"""WS-104 contract tests for the namespaced DAG.

These tests are the proof for the WS-104 DoD:

- Namespacing implemented and unit-tested.
- Cross-scenario isolation verified.
- Cross-tenant isolation verified.

Plus the explicit step-3 isolation invariants and the step-4 causal
ordering check from the issue.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from almighty_kernel import (
    KernelEvent,
    MissingNamespaceError,
    NamespaceMismatchError,
    NamespacedDag,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _event(
    *,
    tenant_id: UUID,
    scenario_id: UUID,
    turn: int = 1,
    action_verb: str = "issue_order",
    officer: str = "COMMANDER",
    source_entity_id: UUID | None = None,
    causal_predecessors: list[UUID] | None = None,
    payload: dict | None = None,
) -> KernelEvent:
    return KernelEvent(
        tenant_id=tenant_id,
        scenario_id=scenario_id,
        turn=turn,
        source_officer_type=officer,
        source_entity_id=source_entity_id or uuid4(),
        action_verb=action_verb,
        payload=payload or {},
        causal_predecessors=causal_predecessors or [],
    )


@pytest.fixture
def dag() -> NamespacedDag:
    return NamespacedDag()


@pytest.fixture
def tenant_a() -> UUID:
    return UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def tenant_b() -> UUID:
    return UUID("99999999-9999-9999-9999-999999999999")


@pytest.fixture
def scenario_x() -> UUID:
    return UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def scenario_y() -> UUID:
    return UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


# ---------------------------------------------------------------------------
# Namespace contract — every commit/read needs both IDs
# ---------------------------------------------------------------------------


def test_read_without_tenant_id_raises(dag: NamespacedDag, scenario_x: UUID) -> None:
    with pytest.raises(MissingNamespaceError) as info:
        dag.read(scenario_id=scenario_x)
    assert "tenant_id" in str(info.value)


def test_read_without_scenario_id_raises(dag: NamespacedDag, tenant_a: UUID) -> None:
    with pytest.raises(MissingNamespaceError) as info:
        dag.read(tenant_id=tenant_a)
    assert "scenario_id" in str(info.value)


def test_read_without_either_raises_naming_both(dag: NamespacedDag) -> None:
    with pytest.raises(MissingNamespaceError) as info:
        dag.read()
    msg = str(info.value)
    assert "tenant_id" in msg and "scenario_id" in msg


def test_topological_order_requires_namespace(dag: NamespacedDag, tenant_a: UUID) -> None:
    with pytest.raises(MissingNamespaceError):
        dag.topological_order(tenant_id=tenant_a)


# ---------------------------------------------------------------------------
# Step 3 — isolation invariants
# ---------------------------------------------------------------------------


def test_isolation_across_scenarios_same_tenant(
    dag: NamespacedDag, tenant_a: UUID, scenario_x: UUID, scenario_y: UUID
) -> None:
    """Write to (T, X), attempt to read from (T, Y) — must return empty."""
    dag.commit(_event(tenant_id=tenant_a, scenario_id=scenario_x))
    dag.commit(_event(tenant_id=tenant_a, scenario_id=scenario_x))
    dag.commit(_event(tenant_id=tenant_a, scenario_id=scenario_x))

    in_x = dag.read(tenant_id=tenant_a, scenario_id=scenario_x)
    in_y = dag.read(tenant_id=tenant_a, scenario_id=scenario_y)

    assert len(in_x) == 3
    assert in_y == []


def test_isolation_across_tenants_same_scenario(
    dag: NamespacedDag, tenant_a: UUID, tenant_b: UUID, scenario_x: UUID
) -> None:
    """Write to (T1, X), attempt to read from (T2, X) — must return empty."""
    dag.commit(_event(tenant_id=tenant_a, scenario_id=scenario_x))
    dag.commit(_event(tenant_id=tenant_a, scenario_id=scenario_x))

    in_a = dag.read(tenant_id=tenant_a, scenario_id=scenario_x)
    in_b = dag.read(tenant_id=tenant_b, scenario_id=scenario_x)

    assert len(in_a) == 2
    assert in_b == []


def test_predecessor_in_other_namespace_is_rejected(
    dag: NamespacedDag, tenant_a: UUID, tenant_b: UUID, scenario_x: UUID
) -> None:
    """A predecessor reference to an event in a different namespace must raise."""
    cross_event = dag.commit(_event(tenant_id=tenant_a, scenario_id=scenario_x))

    with pytest.raises(NamespaceMismatchError) as info:
        dag.commit(
            _event(
                tenant_id=tenant_b,
                scenario_id=scenario_x,
                causal_predecessors=[cross_event.event_id],
            )
        )
    assert "namespace" in str(info.value).lower()


def test_unknown_predecessor_raises_keyerror(
    dag: NamespacedDag, tenant_a: UUID, scenario_x: UUID
) -> None:
    with pytest.raises(KeyError):
        dag.commit(
            _event(
                tenant_id=tenant_a,
                scenario_id=scenario_x,
                causal_predecessors=[uuid4()],
            )
        )


# ---------------------------------------------------------------------------
# Step 4 — causal ordering preserved
# ---------------------------------------------------------------------------


def test_causal_ordering_preserved_for_5_event_chain(
    dag: NamespacedDag, tenant_a: UUID, scenario_x: UUID
) -> None:
    """Emit 5 events with explicit causal_predecessors. Topological order
    must match the declared DAG.

    Declared shape (linear chain to keep the assertion deterministic):

        e1 → e2 → e3 → e4 → e5
    """
    e1 = dag.commit(
        _event(
            tenant_id=tenant_a,
            scenario_id=scenario_x,
            action_verb="issue_order",
        )
    )
    e2 = dag.commit(
        _event(
            tenant_id=tenant_a,
            scenario_id=scenario_x,
            action_verb="detect",
            officer="SENSOR",
            causal_predecessors=[e1.event_id],
        )
    )
    e3 = dag.commit(
        _event(
            tenant_id=tenant_a,
            scenario_id=scenario_x,
            action_verb="track",
            officer="SENSOR",
            causal_predecessors=[e2.event_id],
        )
    )
    e4 = dag.commit(
        _event(
            tenant_id=tenant_a,
            scenario_id=scenario_x,
            action_verb="engage",
            officer="EFFECTOR",
            causal_predecessors=[e3.event_id],
        )
    )
    e5 = dag.commit(
        _event(
            tenant_id=tenant_a,
            scenario_id=scenario_x,
            action_verb="report",
            officer="COMMUNICATOR",
            causal_predecessors=[e4.event_id],
        )
    )

    ordered = dag.topological_order(tenant_id=tenant_a, scenario_id=scenario_x)

    expected_ids = [e1.event_id, e2.event_id, e3.event_id, e4.event_id, e5.event_id]
    assert [ev.event_id for ev in ordered] == expected_ids


def test_diamond_dag_topological_order_respects_partial_order(
    dag: NamespacedDag, tenant_a: UUID, scenario_x: UUID
) -> None:
    """Non-linear case: e1 has two children e2, e3 that both feed e4. Topological
    order must place e1 first, then e2 and e3 (in some order), then e4.
    """
    e1 = dag.commit(_event(tenant_id=tenant_a, scenario_id=scenario_x, action_verb="root"))
    e2 = dag.commit(
        _event(
            tenant_id=tenant_a,
            scenario_id=scenario_x,
            action_verb="branch_a",
            causal_predecessors=[e1.event_id],
        )
    )
    e3 = dag.commit(
        _event(
            tenant_id=tenant_a,
            scenario_id=scenario_x,
            action_verb="branch_b",
            causal_predecessors=[e1.event_id],
        )
    )
    e4 = dag.commit(
        _event(
            tenant_id=tenant_a,
            scenario_id=scenario_x,
            action_verb="join",
            causal_predecessors=[e2.event_id, e3.event_id],
        )
    )

    ordered_ids = [
        ev.event_id
        for ev in dag.topological_order(tenant_id=tenant_a, scenario_id=scenario_x)
    ]

    # e1 first, e4 last; e2 and e3 in any order between
    assert ordered_ids[0] == e1.event_id
    assert ordered_ids[-1] == e4.event_id
    assert set(ordered_ids[1:3]) == {e2.event_id, e3.event_id}


# ---------------------------------------------------------------------------
# Misc surface
# ---------------------------------------------------------------------------


def test_namespaces_listing(dag: NamespacedDag, tenant_a: UUID, tenant_b: UUID, scenario_x: UUID, scenario_y: UUID) -> None:
    dag.commit(_event(tenant_id=tenant_a, scenario_id=scenario_x))
    dag.commit(_event(tenant_id=tenant_a, scenario_id=scenario_y))
    dag.commit(_event(tenant_id=tenant_b, scenario_id=scenario_x))

    namespaces = set(dag.namespaces())
    assert namespaces == {
        (tenant_a, scenario_x),
        (tenant_a, scenario_y),
        (tenant_b, scenario_x),
    }
    assert len(dag) == 3


def test_read_returns_kernel_event_shape(
    dag: NamespacedDag, tenant_a: UUID, scenario_x: UUID
) -> None:
    committed = dag.commit(
        _event(
            tenant_id=tenant_a,
            scenario_id=scenario_x,
            turn=3,
            action_verb="detect",
            officer="SENSOR",
            payload={"detected_entity_id": "x", "confidence": 0.9},
        )
    )
    [readback] = dag.read(tenant_id=tenant_a, scenario_id=scenario_x)
    assert readback.event_id == committed.event_id
    assert readback.tenant_id == tenant_a
    assert readback.scenario_id == scenario_x
    assert readback.turn == 3
    assert readback.action_verb == "detect"
    assert readback.source_officer_type == "SENSOR"
    assert readback.payload == {"detected_entity_id": "x", "confidence": 0.9}


def test_invalid_action_verb_rejected(tenant_a: UUID, scenario_x: UUID) -> None:
    with pytest.raises(ValueError):
        KernelEvent(
            tenant_id=tenant_a,
            scenario_id=scenario_x,
            turn=1,
            source_officer_type="SENSOR",
            source_entity_id=uuid4(),
            action_verb="   ",  # whitespace only
        )


def test_invalid_officer_type_rejected(tenant_a: UUID, scenario_x: UUID) -> None:
    with pytest.raises(ValueError):
        KernelEvent(
            tenant_id=tenant_a,
            scenario_id=scenario_x,
            turn=1,
            source_officer_type="GHOST",  # type: ignore[arg-type]
            source_entity_id=uuid4(),
            action_verb="detect",
        )
