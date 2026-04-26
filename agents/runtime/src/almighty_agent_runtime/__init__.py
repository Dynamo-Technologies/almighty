"""Almighty agent runtime harness (WS-401).

Public API:
    enqueue_turn(...)   — schedule blue -> red -> white chain on the tenant queue
    make_app(...)       — build a Celery app for tests / one-off usage
    start_worker(...)   — programmatic worker startup (CLI is `almighty-runtime-worker`)
"""

from almighty_agent_runtime.celery_app import make_app, tenant_queue_name
from almighty_agent_runtime.dispatch import enqueue_turn
from almighty_agent_runtime.errors import (
    NamespaceMismatchError,
    RuntimeConfigError,
)
from almighty_agent_runtime.wiring import register_noop_crews, register_real_crews
from almighty_agent_runtime.worker import start_worker

__all__ = [
    "make_app",
    "tenant_queue_name",
    "enqueue_turn",
    "register_real_crews",
    "register_noop_crews",
    "start_worker",
    "NamespaceMismatchError",
    "RuntimeConfigError",
]
