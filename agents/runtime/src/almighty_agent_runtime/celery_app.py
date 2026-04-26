"""Celery app singleton + helpers.

Deployment shape: one worker process per tenant. Each worker subscribes
ONLY to its tenant's queue ``almighty:tenant:<tid>:turn-jobs``.
Cross-tenant isolation is therefore enforced at the broker by queue
routing — the in-task tenant_id assertion in :mod:`tasks` is defense
in depth.

The ``app`` here is a module-level singleton because Celery's
``@app.task`` decoration needs to bind at import time. Production
configures it via :func:`configure_app` from ``worker.main``; tests
flip ``task_always_eager = True`` and use a dummy broker.
"""

from __future__ import annotations

from celery import Celery

QUEUE_PREFIX = "almighty:tenant:"
QUEUE_SUFFIX = ":turn-jobs"


def tenant_queue_name(tenant_id: str) -> str:
    """Return the canonical queue name for the given tenant."""
    return f"{QUEUE_PREFIX}{tenant_id}{QUEUE_SUFFIX}"


# Module-level singleton. Configured at import time with placeholder
# broker; production overrides via configure_app() below before starting
# a worker. Tests flip task_always_eager.
app = Celery(
    "almighty-agent-runtime",
    broker="memory://",
    backend="rpc://",
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="almighty:default",
    worker_disable_rate_limits=True,
)


def configure_app(
    *,
    redis_url: str,
    task_always_eager: bool = False,
) -> Celery:
    """Reconfigure the singleton against a real broker.

    Called once at process startup by the worker CLI, or from a test
    fixture that wants to switch from eager to a real broker.
    """
    app.conf.update(
        broker_url=redis_url,
        result_backend=redis_url,
        task_always_eager=task_always_eager,
        task_eager_propagates=task_always_eager,
    )
    return app


def make_app(
    *,
    redis_url: str,
    task_always_eager: bool = False,
) -> Celery:
    """Backwards-compatible alias for :func:`configure_app`. Returns the
    singleton ``app`` after applying the requested configuration.
    """
    return configure_app(redis_url=redis_url, task_always_eager=task_always_eager)
