"""Environment-driven configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from almighty_agent_runtime.errors import RuntimeConfigError


@dataclass(frozen=True)
class RuntimeConfig:
    """Per-process runtime config.

    Attributes:
        tenant_id: The tenant this worker belongs to. Set by the worker CLI.
        redis_url: Celery broker + backend URL.
        control_plane_url: Base URL for the control plane (e.g.,
            "http://control-plane:4000"). Crew-done callbacks POST here.
        request_timeout_s: HTTP timeout for control-plane callbacks.
    """

    tenant_id: str
    redis_url: str
    control_plane_url: str
    request_timeout_s: float = 5.0

    @staticmethod
    def from_env(
        tenant_id: str | None = None,
        env: dict[str, str] | None = None,
    ) -> "RuntimeConfig":
        e = env if env is not None else os.environ
        tid = tenant_id or e.get("ALMIGHTY_WORKER_TENANT_ID")
        if not tid:
            raise RuntimeConfigError(
                "tenant_id required (CLI flag or ALMIGHTY_WORKER_TENANT_ID env)"
            )
        redis_url = e.get("REDIS_URL")
        if not redis_url:
            raise RuntimeConfigError("REDIS_URL is required")
        control_plane_url = e.get("CONTROL_PLANE_URL")
        if not control_plane_url:
            raise RuntimeConfigError("CONTROL_PLANE_URL is required")
        timeout = float(e.get("REQUEST_TIMEOUT_S", "5.0"))
        return RuntimeConfig(
            tenant_id=tid,
            redis_url=redis_url,
            control_plane_url=control_plane_url.rstrip("/"),
            request_timeout_s=timeout,
        )
