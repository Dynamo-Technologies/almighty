"""Turn-controller-side dispatcher.

The turn controller (WS-302) calls :func:`enqueue_turn` once per turn.
That builds a Celery chain ``blue -> red -> white`` routed onto the
tenant's queue. Each task in the chain runs sequentially: Celery only
hands off to the next when the previous succeeds.
"""

from __future__ import annotations

from celery import chain
from celery.canvas import Signature
from celery.result import AsyncResult

from almighty_agent_runtime.celery_app import tenant_queue_name
from almighty_agent_runtime.tasks import run_blue_crew, run_red_crew, run_white_crew


def enqueue_turn(
    *,
    tenant_id: str,
    scenario_id: str,
    turn: int,
) -> AsyncResult:
    """Enqueue the blue -> red -> white chain for the given turn.

    Returns the Celery ``AsyncResult`` for the *terminal* task (white).
    Callers can poll or chain further off it.
    """
    payload = {
        "tenant_id": tenant_id,
        "scenario_id": scenario_id,
        "turn": turn,
    }
    queue = tenant_queue_name(tenant_id)
    sig = chain(
        _signed(run_blue_crew, payload, queue),
        _signed(run_red_crew, payload, queue),
        _signed(run_white_crew, payload, queue),
    )
    return sig.apply_async()


def _signed(task, payload, queue: str) -> Signature:
    """The first task takes ``payload`` directly; subsequent tasks in the
    chain receive ``payload`` from the previous task's return value, so
    they're called with no positional args at signature time.
    """
    if task is run_blue_crew:
        return task.s(payload).set(queue=queue)
    return task.s().set(queue=queue)
