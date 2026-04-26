"""Celery tasks for between-turn execution.

Three tasks, one per crew side. The turn controller dispatches a chain
``blue -> red -> white`` onto the tenant's queue; each task runs the
appropriate crew, posts a completion callback, and (via Celery's chain
machinery) hands off to the next.

Isolation invariant: every task verifies that
``payload['tenant_id'] == os.environ['ALMIGHTY_WORKER_TENANT_ID']``
before doing real work. The Celery queue routing is the primary
boundary; this assertion catches misrouted messages and refuses to
process them.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from almighty_agent_runtime.celery_app import app
from almighty_agent_runtime.control_plane import post_crew_done
from almighty_agent_runtime.crews import CrewContext, get_crew_runner
from almighty_agent_runtime.errors import NamespaceMismatchError

LOG = logging.getLogger(__name__)

JobPayload = dict[str, Any]


def _assert_tenant_match(payload: JobPayload) -> None:
    """Defense-in-depth: confirm this worker's tenant matches the job's.

    The Celery queue routing already filters by tenant — this check
    catches cases where a worker was started with a different
    ALMIGHTY_WORKER_TENANT_ID than its queue subscription, or where a
    misconfigured caller dropped a payload onto the wrong queue.

    Skipped when ``ALMIGHTY_WORKER_TENANT_ID`` is unset, so tests using
    eager mode without a worker process can run without this env var.
    """
    expected = os.environ.get("ALMIGHTY_WORKER_TENANT_ID")
    if expected is None:
        return
    payload_tid = payload.get("tenant_id")
    if payload_tid != expected:
        raise NamespaceMismatchError(
            f"worker tenant_id={expected!r} but payload tenant_id={payload_tid!r}"
        )


def _run_crew(crew_name: str, payload: JobPayload) -> JobPayload:
    """Shared body for the three crew tasks.

    Runs the crew, posts the completion callback, and returns the
    payload unchanged so Celery's chain hands it off to the next task.
    Returning the payload (rather than the crew result) is intentional —
    the next task in the chain wants the same job descriptor, not the
    previous crew's metadata.
    """
    _assert_tenant_match(payload)

    tenant_id: str = payload["tenant_id"]
    scenario_id: str = payload["scenario_id"]
    turn: int = payload["turn"]

    started = time.perf_counter()
    runner = get_crew_runner(crew_name)  # type: ignore[arg-type]
    result = runner(
        CrewContext(tenant_id=tenant_id, scenario_id=scenario_id, turn=turn)
    )
    duration_ms = int((time.perf_counter() - started) * 1000)

    # POST callback. Soft-fails to a log line if the endpoint isn't ready
    # yet — see control_plane.py docstring.
    control_plane_url = os.environ.get("CONTROL_PLANE_URL")
    if control_plane_url:
        post_crew_done(
            control_plane_url=control_plane_url,
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            turn=turn,
            crew=crew_name,
            payload={
                "duration_ms": duration_ms,
                "notes": result.notes,
                "metadata": result.metadata,
            },
        )
    else:
        LOG.info(
            "CONTROL_PLANE_URL unset; skipping callback crew=%s tenant=%s",
            crew_name,
            tenant_id,
        )

    return payload


@app.task(name="almighty.runtime.run_blue_crew", bind=False)
def run_blue_crew(payload: JobPayload) -> JobPayload:
    return _run_crew("blue", payload)


@app.task(name="almighty.runtime.run_red_crew", bind=False)
def run_red_crew(payload: JobPayload) -> JobPayload:
    return _run_crew("red", payload)


@app.task(name="almighty.runtime.run_white_crew", bind=False)
def run_white_crew(payload: JobPayload) -> JobPayload:
    return _run_crew("white", payload)
