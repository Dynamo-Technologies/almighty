"""Shared pytest setup.

Tests run in Celery's eager mode — no live broker, no worker process,
no Redis. Tasks execute synchronously inline at ``apply_async`` time.
This is sufficient for the WS-401 DoD because the chain semantics and
queue-routing decisions are deterministic in eager mode; the things
eager mode *can't* exercise (real broker, multi-process isolation) are
out of scope for v1.

Tests that need real Redis can opt in by setting ``USE_REAL_REDIS=1``
and running ``docker run --rm -d --name almighty-runtime-redis -p
6380:6379 redis:7-alpine``. None of the in-tree tests do today.
"""

from __future__ import annotations

import os

import pytest

from almighty_agent_runtime.celery_app import configure_app


@pytest.fixture(autouse=True)
def _eager_celery():
    """Force eager mode for every test in the suite.

    Broker stays ``memory://`` (in-process, fine for eager); backend
    stays ``rpc://`` because eager mode still hands the result through
    the result-store interface and a true ``memory://`` backend doesn't
    exist as a Celery package.
    """
    from almighty_agent_runtime.celery_app import app as _app
    _app.conf.update(
        broker_url="memory://",
        result_backend="rpc://",
        task_always_eager=True,
        task_eager_propagates=True,
    )
    yield
    # Clear the worker tenant env so tests don't leak state into each other.
    os.environ.pop("ALMIGHTY_WORKER_TENANT_ID", None)
    os.environ.pop("CONTROL_PLANE_URL", None)
