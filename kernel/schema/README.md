# Almighty kernel — schema stubs

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

This directory contains DDL stubs for the kernel's authoritative tables.
They are **not migrations yet**. The migration framework lands with the
control plane (WS-301 / #17) — likely `node-pg-migrate` per the
`services/control-plane/` plan in `docs/dummy-instructions.md`.

Until then, these `.sql` files are committed for two reasons:

1. **Review.** They are the executable companion to
   `docs/schema/entity-event.md` and let reviewers exercise the schema
   constraints against a scratch Postgres without spinning up the control
   plane.
2. **Anchor.** Subsequent kernel work — the PyRapide DAG namespacing
   (WS-104), the officer interface tools (WS-402), the live CZML adapter
   (WS-503) — references these column names directly. Pinning them now
   means the downstream issues don't drift on naming.

## Files

| File | What it defines |
|---|---|
| `entities.sql` | `force_affiliation` and `entity_type_category` enums; `entities` table with all positional / kinematic / capability columns; the shared `almighty_set_updated_at()` trigger function. |
| `events.sql` | `officer_type` enum; `events` table; cross-table FK on `(tenant_id, scenario_id, source_entity_id)`; predecessor-cross-scenario validation trigger function (declared but not yet attached). |

`entities.sql` MUST be loaded before `events.sql` because the events table
has a composite FK into entities.

## Local exercise

To play with the DDL against a scratch Postgres:

```bash
# Spin up an ephemeral Postgres
docker run --rm -d --name almighty-pg-scratch \
  -e POSTGRES_PASSWORD=scratch \
  -p 5433:5432 \
  postgres:16

# Wait a beat for it to come up
until docker exec almighty-pg-scratch pg_isready -U postgres; do sleep 1; done

# Required extension for gen_random_uuid()
docker exec -i almighty-pg-scratch psql -U postgres -d postgres \
  -c 'CREATE EXTENSION IF NOT EXISTS pgcrypto;'

# Load the DDL
docker exec -i almighty-pg-scratch psql -U postgres -d postgres < entities.sql
docker exec -i almighty-pg-scratch psql -U postgres -d postgres < events.sql

# Eyeball
docker exec -it almighty-pg-scratch psql -U postgres -d postgres -c '\d entities'
docker exec -it almighty-pg-scratch psql -U postgres -d postgres -c '\d events'

# Cleanup
docker rm -f almighty-pg-scratch
```

## Constraints intentionally deferred

These are NOT bugs in the stubs — they are tracked items belonging to other
issues:

- **`action_verb` enum.** The full 20-verb vocabulary lives in WS-105 (#9).
  When that lands, an `ALTER TABLE events ADD CONSTRAINT` adds the CHECK.
  The TODO comment in `events.sql` carries the verb list for reference.
- **Cross-scenario predecessor validation.** The trigger function is
  defined but not attached. WS-104 (#8) owns the decision to enable it
  after measuring write-path cost; until then, application code in the
  kernel commit path enforces the invariant.
- **Row-level security.** Per-tenant + per-scenario RLS policies are owned
  by WS-301 (#17) since they need a session GUC populated by the control
  plane's auth middleware.
- **`capability_set_ref` validation.** The text reference is unenforced
  until WS-106 (#10) lands the capability profile registry.

## Naming conventions

- Tables: snake_case singular has been the recurring debate; we use
  **plural** here (`entities`, `events`) for compatibility with most ORMs
  and to match the imperative naming in `docs/schema/entity-event.md`.
- Enum types: snake_case singular (`force_affiliation`, `officer_type`).
- Indexes: `<table>_<purpose>_idx`.
- Constraints: `<table>_<column-or-purpose>_<kind>` (e.g.,
  `entities_orientation_unit_quat`).

## References

- Schema spec: [`docs/schema/entity-event.md`](../../docs/schema/entity-event.md)
- Glossary: [`docs/glossary.md`](../../docs/glossary.md)
- Migrations owner: WS-301 (#17)
- Action verb owner: WS-105 (#9)
- Capability profile owner: WS-106 (#10)
