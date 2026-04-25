# Almighty kernel

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

The Almighty kernel is the Tier 4 layer of the platform. It owns:

- The neutral entity/event schema (WS-101) — `kernel/schema/`.
- The capability profile library (WS-107) — `kernel/capability-profiles/`.
- The tenant/scenario-namespaced causal DAG built on top of [PyRapide](https://pypi.org/project/pyrapide/) (WS-104) — `kernel/almighty_kernel/`.

This README documents the namespaced DAG. Schema and capability work
have their own READMEs.

## Quick start

```bash
# Requires Python 3.11+. The kernel is published as a local package.
python3 -m venv .venv
source .venv/bin/activate
pip install -e kernel/
pytest kernel/tests/
```

## Why namespaced

The simulation runs many scenarios across many tenants concurrently. The
control plane (WS-301) and the agent runtime (WS-401) both partition by
`(tenant_id, scenario_id)`. The kernel DAG is the source of truth for
causal history — if it leaked across either boundary, the override
gateway, AAR replay, and tenant isolation guarantees would all break.

PyRapide's `Poset` is a single causal DAG. The Almighty kernel partitions
it: each `(tenant_id, scenario_id)` namespace gets its own `Poset`, kept
in a dict on the wrapper. There is **no shared event store** across
namespaces — cross-namespace leakage is structurally impossible because
no read path can return events from outside the namespace's own Poset.

## Public API

```python
from almighty_kernel import (
    KernelEvent,
    NamespacedDag,
    MissingNamespaceError,
    NamespaceMismatchError,
)
```

### `KernelEvent`

Pydantic model that mirrors the WS-101 event schema. Required fields:
`tenant_id`, `scenario_id`, `turn`, `source_officer_type`,
`source_entity_id`, `action_verb`. Optional: `event_id` (auto-uuid4),
`payload` (`{}`), `causal_predecessors` (`[]`), `ts` (now-utc).

`source_officer_type` is constrained to the five-element enum from
[`docs/glossary.md`](../docs/glossary.md#1-officer-types):
`SENSOR`, `EFFECTOR`, `MOVER`, `COMMUNICATOR`, `COMMANDER`.

`action_verb` is unconstrained text in v1 — WS-105 (#9) will lock it down.

### `NamespacedDag`

```python
dag = NamespacedDag()

# Commit
dag.commit(KernelEvent(tenant_id=..., scenario_id=..., ...))

# Read (insertion order)
dag.read(tenant_id=..., scenario_id=...)

# Read in causal (topological) order
dag.topological_order(tenant_id=..., scenario_id=...)

# Diagnostic
dag.namespaces()  # list of (tenant_id, scenario_id)
len(dag)          # total events across all namespaces
```

Every method that touches events requires both `tenant_id` and
`scenario_id`. Missing either raises
[`MissingNamespaceError`](almighty_kernel/errors.py).

A `causal_predecessors` reference to an event in a different namespace
raises `NamespaceMismatchError`.

A `causal_predecessors` reference to an unknown `event_id` raises
`KeyError` — the kernel does not silently accept dangling predecessors.

## Isolation guarantees

The WS-104 contract is verified by the test suite at
`kernel/tests/test_namespacing.py`:

| Invariant | Test | Status |
|---|---|---|
| Read without `tenant_id` raises | `test_read_without_tenant_id_raises` | ✅ |
| Read without `scenario_id` raises | `test_read_without_scenario_id_raises` | ✅ |
| Cross-scenario read returns empty | `test_isolation_across_scenarios_same_tenant` | ✅ |
| Cross-tenant read returns empty | `test_isolation_across_tenants_same_scenario` | ✅ |
| Cross-namespace predecessor rejected | `test_predecessor_in_other_namespace_is_rejected` | ✅ |
| Unknown predecessor rejected | `test_unknown_predecessor_raises_keyerror` | ✅ |
| Linear 5-event chain ordered correctly | `test_causal_ordering_preserved_for_5_event_chain` | ✅ |
| Diamond DAG ordered correctly | `test_diamond_dag_topological_order_respects_partial_order` | ✅ |

Run them locally with `pytest kernel/tests/`.

## Known limits

These are intentional v1 constraints, not bugs. Each is owned by a future
issue.

- **In-memory only.** The DAG lives entirely in process memory. There is
  no persistence layer here — durability is the responsibility of the
  control plane (WS-301), which writes committed events to the per-tenant
  Postgres `events` table per the WS-101 schema. The kernel is the
  in-memory shape; Postgres is the system of record.
- **No rollback / branching.** Once an event is committed to a Poset, it
  cannot be removed. Scenario rollback for what-if branching is on the
  Phase 6+ roadmap; it will require copy-on-write Posets, not in-place
  mutation. **There is no rollback API today and adding one is non-trivial.**
- **Replay loads from durable storage.** AAR replay (WS-506) and turn
  rewinds are implemented by reading committed events from the per-tenant
  Postgres and re-walking the DAG. Replay is therefore not "scrub the
  in-memory DAG backwards" — it is "rebuild a fresh DAG up to turn N from
  the events table."
- **Predecessor-cross-scenario validation is application-side.** The
  WS-101 SQL ships a trigger function but leaves it unattached. The
  kernel here does the same check in Python at commit time. Once
  benchmarks for the trigger are in (this issue's follow-up if needed),
  the trigger can be enabled and the Python check kept as defense in
  depth.
- **`action_verb` is unconstrained text.** WS-105 (#9) will lock the
  vocabulary; until then the kernel only checks non-emptiness.
- **No concurrency control.** A single `NamespacedDag` instance is not
  thread-safe. The agent runtime (WS-401) gives each tenant its own
  worker process, so a single-instance assumption is safe per-tenant.
  Multi-process / multi-host coordination is again the durable-store
  problem (WS-301).
- **No emission to the WebSocket fan-out.** This kernel does not push
  events anywhere. The CZML adapter (WS-503) and the WebSocket fan-out
  (WS-304) sit between the kernel and consumers.

## Project layout

```
kernel/
├── almighty_kernel/          # Python package — namespaced DAG wrapper
│   ├── __init__.py           # public re-exports
│   ├── dag.py                # KernelEvent + NamespacedDag
│   └── errors.py             # MissingNamespaceError, NamespaceMismatchError
├── capability-profiles/      # JSON profiles per WS-106 / WS-107 (TBD)
├── schema/                   # SQL DDL stubs per WS-101
├── tests/
│   └── test_namespacing.py   # WS-104 contract tests
├── pyproject.toml
└── README.md                 # this file
```

## References

- Upstream PyRapide: <https://github.com/ShaneDolphin/pyrapide>
- Schema spec: [`docs/schema/entity-event.md`](../docs/schema/entity-event.md)
- Glossary: [`docs/glossary.md`](../docs/glossary.md)
- Architecture: [`docs/architecture.md`](../docs/architecture.md)

## Downstream consumers

- WS-105 (#9) — officer interface verbs will tighten `action_verb` to a CHECK.
- WS-301 (#17) — control plane persists committed events into per-tenant Postgres.
- WS-303 (#19) — override gateway intercepts events between WS-402 tools and `commit()`.
- WS-401 (#21) — agent runtime gives each tenant its own DAG instance.
- WS-402 (#22) — officer tools call `commit()` after capability gating.
- WS-503 (#28) — live CZML adapter walks the DAG and projects effect-bound events to packets.
- WS-506 (#31) — AAR replay rebuilds a fresh DAG from durable storage.
