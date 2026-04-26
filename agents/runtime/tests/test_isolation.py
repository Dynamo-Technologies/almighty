"""Isolation invariants.

The Celery queue routing is the primary cross-tenant boundary — each
worker subscribes only to ``almighty:tenant:<tid>:turn-jobs``. This test
exercises the in-task defense-in-depth check that catches misrouted
payloads when ``ALMIGHTY_WORKER_TENANT_ID`` is set.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from almighty_agent_runtime.celery_app import tenant_queue_name
from almighty_agent_runtime.errors import NamespaceMismatchError
from almighty_agent_runtime.tasks import run_blue_crew


def test_queue_name_format():
    tid = "11111111-1111-1111-1111-111111111111"
    assert tenant_queue_name(tid) == f"almighty:tenant:{tid}:turn-jobs"


def test_task_rejects_payload_with_mismatched_tenant_id():
    """Worker is configured for tenant A; a payload from tenant B raises."""
    tenant_a = str(uuid4())
    tenant_b = str(uuid4())
    os.environ["ALMIGHTY_WORKER_TENANT_ID"] = tenant_a

    payload_for_b = {
        "tenant_id": tenant_b,
        "scenario_id": str(uuid4()),
        "turn": 1,
    }

    with pytest.raises(NamespaceMismatchError) as info:
        run_blue_crew.apply(args=[payload_for_b]).get(propagate=True)
    assert tenant_a in str(info.value)
    assert tenant_b in str(info.value)


def test_task_accepts_payload_with_matching_tenant_id():
    tenant_a = str(uuid4())
    os.environ["ALMIGHTY_WORKER_TENANT_ID"] = tenant_a

    payload = {
        "tenant_id": tenant_a,
        "scenario_id": str(uuid4()),
        "turn": 1,
    }

    result = run_blue_crew.apply(args=[payload])
    assert result.successful()
    assert result.get(propagate=True) == payload


def test_task_skips_assertion_when_worker_tenant_unset():
    """The env-var-not-set escape hatch lets pure unit tests run without
    setting ALMIGHTY_WORKER_TENANT_ID. The check only fires in worker
    processes.
    """
    os.environ.pop("ALMIGHTY_WORKER_TENANT_ID", None)
    payload = {"tenant_id": str(uuid4()), "scenario_id": str(uuid4()), "turn": 0}
    result = run_blue_crew.apply(args=[payload])
    assert result.successful()
