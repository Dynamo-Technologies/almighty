"""End-to-end runner test with stub stream + sink.

Verifies the runner glues translator outputs to publish / publish_rejected
correctly, and that SKIPPED events go nowhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import pytest

from almighty_kernel.dag import KernelEvent

from almighty_czml_adapter.runner import AdapterRunner

from conftest import make_event


@dataclass
class _StreamFromList:
    events: list[KernelEvent]

    def __aiter__(self) -> AsyncIterator[KernelEvent]:
        async def gen() -> AsyncIterator[KernelEvent]:
            for e in self.events:
                yield e

        return gen()


@dataclass
class _CollectingSink:
    accepted: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    rejected: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    async def publish(self, *, tenant_id: str, packet: dict[str, Any]) -> None:
        self.accepted.append((tenant_id, packet))

    async def publish_rejected(self, *, tenant_id: str, rejection: dict[str, Any]) -> None:
        self.rejected.append((tenant_id, rejection))


@pytest.mark.asyncio
async def test_runner_routes_accepted_packets(
    template_loader, validator, us_bct_profile, position
):
    accepted_event = make_event(
        action_verb="engage",
        source_officer_type="EFFECTOR",
        payload={
            "weapon_system": "notional.indirect.medium",
            "volume_count": 1,
            "range_m": 5_000.0,
            "time_of_flight_s": 15.0,
            "dispersion_ellipse_a_m": 50.0,
            "dispersion_ellipse_b_m": 50.0,
        },
    )
    skipped_event = make_event(action_verb="move_to", source_officer_type="MOVER")
    rejected_event = make_event(
        action_verb="engage",
        source_officer_type="EFFECTOR",
        payload={
            "weapon_system": "notional.indirect.medium",
            "volume_count": 1,
            "range_m": 50_000.0,  # over us-bct cap → reject
            "time_of_flight_s": 30.0,
            "dispersion_ellipse_a_m": 50.0,
            "dispersion_ellipse_b_m": 50.0,
        },
    )

    sink = _CollectingSink()
    runner = AdapterRunner(
        stream=_StreamFromList([accepted_event, skipped_event, rejected_event]),
        sink=sink,
        validator=validator,
        template_loader=template_loader,
        capability_profile=us_bct_profile,
        entity_position_lookup=lambda _e: position,
    )
    await runner.run()

    assert len(sink.accepted) == 1
    tenant_id, packet = sink.accepted[0]
    assert tenant_id == str(accepted_event.tenant_id)
    assert packet["id"]  # substituted artifact_id

    assert len(sink.rejected) == 1
    rej_tenant, rejection = sink.rejected[0]
    assert rej_tenant == str(rejected_event.tenant_id)
    assert rejection["family"] == "indirect_fire_arc"
    assert "range_m" in rejection["reason"]
    assert "rejected_at" in rejection


@pytest.mark.asyncio
async def test_runner_handles_empty_stream(
    template_loader, validator, us_bct_profile
):
    sink = _CollectingSink()
    runner = AdapterRunner(
        stream=_StreamFromList([]),
        sink=sink,
        validator=validator,
        template_loader=template_loader,
        capability_profile=us_bct_profile,
    )
    await runner.run()
    assert sink.accepted == []
    assert sink.rejected == []
