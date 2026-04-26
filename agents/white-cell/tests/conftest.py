"""Shared fixtures."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from almighty_agent_runtime.crews import CrewContext
from almighty_kernel.dag import KernelEvent

TENANT = UUID("11111111-1111-4111-8111-111111111111")
SCENARIO = UUID("22222222-2222-4222-8222-222222222222")


@pytest.fixture()
def crew_ctx() -> CrewContext:
    return CrewContext(
        tenant_id=str(TENANT), scenario_id=str(SCENARIO), turn=1
    )


def make_event(
    *,
    action_verb: str,
    source_officer_type: str,
    payload: dict | None = None,
    turn: int = 1,
    source_entity_id: UUID | None = None,
) -> KernelEvent:
    """Convenience for tests — constructs a KernelEvent in the canonical
    test namespace."""
    return KernelEvent(
        event_id=uuid4(),
        tenant_id=TENANT,
        scenario_id=SCENARIO,
        turn=turn,
        source_officer_type=source_officer_type,
        source_entity_id=source_entity_id or uuid4(),
        action_verb=action_verb,
        payload=payload or {},
        causal_predecessors=[],
    )
