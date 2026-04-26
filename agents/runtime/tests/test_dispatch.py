"""Dispatch surface — confirm queue routing and signature shapes."""

from __future__ import annotations

from uuid import uuid4

from almighty_agent_runtime import enqueue_turn
from almighty_agent_runtime.celery_app import tenant_queue_name


def test_enqueue_turn_routes_to_tenant_queue(monkeypatch):
    """The chain's first task (blue) must carry the tenant's queue name
    in its options. This is what makes one tenant's worker NOT pick up
    another tenant's job.
    """
    captured: list[dict] = []

    from celery.canvas import _chain  # type: ignore[attr-defined]

    real_apply_async = _chain.apply_async

    def spy(self, *args, **kwargs):
        # Walk the chain and record each task's queue option.
        for sig in self.tasks:
            captured.append(
                {
                    "name": sig.task,
                    "queue": sig.options.get("queue"),
                }
            )
        return real_apply_async(self, *args, **kwargs)

    monkeypatch.setattr(_chain, "apply_async", spy)

    tenant_id = str(uuid4())
    expected_queue = tenant_queue_name(tenant_id)

    enqueue_turn(
        tenant_id=tenant_id,
        scenario_id=str(uuid4()),
        turn=0,
    )

    assert len(captured) == 3
    for entry in captured:
        assert entry["queue"] == expected_queue, entry
    names = [e["name"] for e in captured]
    assert names == [
        "almighty.runtime.run_blue_crew",
        "almighty.runtime.run_red_crew",
        "almighty.runtime.run_white_crew",
    ]
