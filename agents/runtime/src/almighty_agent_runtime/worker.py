"""Worker process entrypoint.

CLI:
    almighty-runtime-worker --tenant-id <uuid> [--concurrency N]

Started per tenant. The worker subscribes only to that tenant's queue
``almighty:tenant:<tid>:turn-jobs``; cross-tenant isolation is enforced
at the broker by queue routing.

# TODO WS-004: assume the per-tenant ECS task role here. The role ARN is
# the ``task_role_arn`` output of the WS-004 Terraform module. Today
# we run with whatever credentials the host process has; in deployed
# Almighty each worker should ``sts:AssumeRole`` into its tenant's
# scoped role before consuming any jobs so a misrouted message can't
# touch another tenant's S3 bucket / RDS / KMS key.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from almighty_agent_runtime.celery_app import (
    app,
    configure_app,
    tenant_queue_name,
)
from almighty_agent_runtime.config import RuntimeConfig

LOG = logging.getLogger(__name__)


def start_worker(
    *,
    config: RuntimeConfig,
    concurrency: int = 1,
    extra_argv: list[str] | None = None,
) -> int:
    """Programmatic worker startup. Returns the worker's exit code.

    Used by the CLI ``main()`` and by tests that want to start a worker
    in a subprocess. Tests typically prefer ``task_always_eager`` mode
    instead and skip this entirely.
    """
    os.environ["ALMIGHTY_WORKER_TENANT_ID"] = config.tenant_id
    os.environ["CONTROL_PLANE_URL"] = config.control_plane_url
    configure_app(redis_url=config.redis_url, task_always_eager=False)

    queue = tenant_queue_name(config.tenant_id)
    argv = [
        "worker",
        "-Q",
        queue,
        "-l",
        "info",
        "-c",
        str(concurrency),
        "-n",
        f"almighty-{config.tenant_id}@%h",
    ]
    if extra_argv:
        argv.extend(extra_argv)
    LOG.info("starting worker tenant=%s queue=%s", config.tenant_id, queue)
    return app.worker_main(argv)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="almighty-runtime-worker",
        description="Almighty between-turn agent runtime worker (WS-401).",
    )
    parser.add_argument("--tenant-id", required=False)
    parser.add_argument("--concurrency", type=int, default=1)
    args, extra = parser.parse_known_args(argv)
    logging.basicConfig(level=logging.INFO)
    config = RuntimeConfig.from_env(tenant_id=args.tenant_id)
    return start_worker(config=config, concurrency=args.concurrency, extra_argv=extra)


if __name__ == "__main__":
    sys.exit(main())
