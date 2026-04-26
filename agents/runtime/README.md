# Almighty agent runtime (WS-401)

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

The between-turn agent execution harness. Owns process lifecycle, queue
routing, and ordering for the blue → red → white crew chain. The actual
crew logic (CrewAI agents) lands in WS-403, WS-404, and WS-405; this
service is the *substrate* those crews run on.

## Stack

- Python ≥ 3.11
- [Celery 5.4](https://docs.celeryq.dev/) — chains, queues, retries
- [Redis 7+](https://redis.io/) — broker and result backend
- [httpx](https://www.python-httpx.org/) — control-plane callback client
- [pydantic 2.6](https://docs.pydantic.dev/) — config validation

### Why Celery (not RQ)

The prompt allowed either; **Celery wins for chain ergonomics**. The
``blue → red → white`` sequencing requirement maps directly onto
Celery's ``chain`` primitive — return value of one task becomes the
input of the next, queue routing is preserved, and a failure in any
link halts the rest of the chain. RQ has weaker chain support; you
hand-roll the sequencing or run a parent job that fires children.

## Architecture

```
            ┌──────────────────────┐         ┌────────────────────────┐
turn        │   turn controller    │         │   control plane (WS-301)│
controller  │   (WS-302) on        │         │                        │
sends a     │   /turns/advance     │         │   /turns/:turn/crews/:c│
job  ──────▶│   calls              │         │   /done callback       │
            │   enqueue_turn(...)  │         └─────────▲──────────────┘
            └─────┬────────────────┘                   │
                  │                                    │ HTTP POST
                  │ Celery chain                       │ on each crew
                  │ blue → red → white                 │ completion
                  │ routed to                          │
                  │ almighty:tenant:<tid>:turn-jobs    │
                  ▼                                    │
            ┌──────────────────────┐                   │
            │   Redis broker       │                   │
            └─────┬────────────────┘                   │
                  │                                    │
                  ▼                                    │
            ┌──────────────────────┐                   │
            │   per-tenant worker  │───────────────────┘
            │   subscribes to      │
            │   only its queue     │
            └──────────────────────┘
```

### Per-tenant worker

One worker process per tenant. Started with:

```bash
ALMIGHTY_WORKER_TENANT_ID=<uuid> \
REDIS_URL=redis://localhost:6379/0 \
CONTROL_PLANE_URL=http://control-plane:4000 \
almighty-runtime-worker --tenant-id <uuid>
```

The worker subscribes ONLY to ``almighty:tenant:<uuid>:turn-jobs``.
Cross-tenant isolation is enforced at the Celery broker by queue
routing — there is no shared queue another tenant's worker could pull
from. The in-task ``ALMIGHTY_WORKER_TENANT_ID`` assertion in
``tasks.py`` is defense in depth: it raises
``NamespaceMismatchError`` if a payload arrives with a foreign
``tenant_id``.

### Job payload

```json
{
  "tenant_id":   "<uuid>",
  "scenario_id": "<uuid>",
  "turn":        7,
  "crew":        "blue"  // implicit; the chain is built per task
}
```

The dispatcher (``enqueue_turn``) attaches the ``crew`` per task as
part of the chain construction; the payload itself stays the same
across the chain.

### Sequential ordering

```python
from almighty_agent_runtime import enqueue_turn

result = enqueue_turn(
    tenant_id="...",
    scenario_id="...",
    turn=7,
)
result.get(timeout=60)  # blocks until white completes
```

Internally:

```python
chain(
    run_blue_crew.s(payload).set(queue=tenant_queue),
    run_red_crew.s().set(queue=tenant_queue),
    run_white_crew.s().set(queue=tenant_queue),
).apply_async()
```

Celery only hands a payload off to the next task when the previous one
returns successfully. A ``NamespaceMismatchError`` from blue halts the
chain immediately — red and white never run.

### Crew-done callback

Each task POSTs to:

```
POST {CONTROL_PLANE_URL}/tenants/{tenant_id}/scenarios/{scenario_id}/turns/{turn}/crews/{crew}/done
{
  "tenant_id":   "...",
  "scenario_id": "...",
  "turn":        7,
  "crew":        "blue",
  "duration_ms": 12,
  "notes":       "noop crew (WS-401 stub)",
  "metadata":    {...}
}
```

The control-plane endpoint that consumes this is owned by a follow-up
to WS-302 (the turn controller's ``runBetweenTurnAgents`` stub will
eventually wait for these callbacks). **Until that endpoint exists,
the harness logs the 404 and continues** so dev iteration isn't blocked.

## Local development

```bash
# 1. Spin up Redis
docker run --rm -d --name almighty-runtime-redis -p 6379:6379 redis:7-alpine

# 2. Install (in a Python 3.11+ venv)
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e "agents/runtime[dev]"

# 3. Run the worker
ALMIGHTY_WORKER_TENANT_ID=00000000-0000-4000-8000-000000000001 \
REDIS_URL=redis://localhost:6379/0 \
CONTROL_PLANE_URL=http://localhost:4000 \
almighty-runtime-worker --tenant-id 00000000-0000-4000-8000-000000000001

# 4. From another shell, dispatch a turn:
python -c "
import os
os.environ['REDIS_URL'] = 'redis://localhost:6379/0'
os.environ['CONTROL_PLANE_URL'] = 'http://localhost:4000'
from almighty_agent_runtime import enqueue_turn, make_app
make_app(redis_url='redis://localhost:6379/0')
enqueue_turn(
    tenant_id='00000000-0000-4000-8000-000000000001',
    scenario_id='00000000-0000-4000-8000-000000000002',
    turn=1,
)
"
```

## Tests

```bash
cd agents/runtime
pytest tests/
```

The suite uses Celery's eager mode — tasks run synchronously inline at
``apply_async`` time, no live broker, no worker process. This is enough
to exercise the chain semantics, queue-routing decisions, callback
shape, and the namespace-mismatch assertion.

| File | What it covers |
|---|---|
| ``tests/test_empty_crew.py`` | **WS-401 DoD**: empty crew chain runs end-to-end and posts all three callbacks in < 2 s. |
| ``tests/test_isolation.py`` | Queue-name format; ``NamespaceMismatchError`` on foreign payload; pass-through when env unset. |
| ``tests/test_chain.py`` | blue → red → white order; chain survives a 404 callback (soft-fail). |
| ``tests/test_dispatch.py`` | Each chain link carries the tenant queue option. |

For a real-broker integration test, set ``USE_REAL_REDIS=1`` and
``REDIS_URL`` and start a Redis. None of the in-tree tests do that
today; opt-in only.

## Open TODOs

- **WS-004 task role assumption.** Each worker should ``sts:AssumeRole``
  into its tenant's scoped role (``task_role_arn`` from the WS-004
  Terraform module) before consuming jobs. v1 runs with whatever
  credentials the host process has. Inline TODO comment in ``worker.py``.
- **Crew-done callback endpoint.** The turn controller (WS-302) will
  eventually expose ``POST /tenants/:id/scenarios/:sid/turns/:turn/crews/:c/done``
  to receive these. Until it does, the harness soft-fails the POST.
  Once it exists, tighten ``control_plane.py`` to surface 4xx as task
  failures.
- **Real CrewAI integration.** ``crews.py`` keeps NoOp stubs as the
  fallback default. ``wiring.register_real_crews()`` (called from
  ``worker.start_worker``) swaps each side's ``"default"`` slot to the
  deterministic runner shipped by WS-403 (blue), WS-404 (red), and
  WS-405 (white-cell) when those packages are installed. Sides whose
  package isn't on the import path keep their no-op fallback so the
  runtime can still be tested in isolation.
- **Retries.** Failed crew tasks halt the chain. v1 doesn't retry;
  white-cell operators inspect logs and re-enqueue. Tracked as a
  follow-up.
- **Per-tenant worker process orchestration.** Spawning workers
  on-demand when a tenant has a scenario in 'advancing' state is a
  deployment concern (likely Kubernetes Job, ECS task, or systemd
  template). Out of scope for v1; the harness itself is process-shape
  agnostic.

## References

- Glossary — between-turn execution: [`docs/glossary.md#between-turn-execution`](../../docs/glossary.md#between-turn-execution)
- Schema: [`docs/schema/entity-event.md`](../../docs/schema/entity-event.md)
- Officer interfaces (downstream): [`docs/schema/officer-interfaces.md`](../../docs/schema/officer-interfaces.md)
- Turn controller (caller): WS-302 (#18) at `services/control-plane/`
- Implementation gotchas: [`docs/better-late-than-never.md`](../../docs/better-late-than-never.md)
