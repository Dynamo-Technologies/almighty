# Almighty control plane

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

The Tier 2 control plane. Today this service exposes only the **WS-302
turn advancement endpoint** plus the substrate (auth, migrations, db
pool) that **WS-301** will extend with tenant + scenario CRUD endpoints.

## Stack

- Node ≥ 20 (`type: module`, native TypeScript via `--experimental-strip-types`)
- Fastify 5
- pg 8 (Postgres 16)
- jose 5 (HS256 JWT verification)
- pino 9 (logger)
- vitest 2 (tests)

## Endpoints

| Method | Path | Auth | Owner |
|---|---|---|---|
| `GET` | `/healthz` | none | WS-302 |
| `POST` | `/tenants/:id/scenarios/:sid/turns/advance` | bearer JWT, `cell_role=white` | WS-302 |

WS-301 (#17) will add CRUD endpoints under `/tenants` and
`/tenants/:id/scenarios` against this same service.

## Auth contract

Bearer JWT signed with HS256 against `JWT_SECRET`. Required claims:

```json
{
  "sub": "<user identifier>",
  "tenant_id": "<uuid>",
  "cell_role": "white | blue | red | observer"
}
```

The turn-advance endpoint enforces:

1. JWT signature valid → else `401`.
2. `cell_role === "white"` → else `403`.
3. JWT `tenant_id === URL :id` → else `403`. (No cross-tenant white-cell action.)

## Migrations

Plain `.sql` files under `migrations/`, applied in lexicographic order
by `src/db/migrate.ts` and tracked in a `schema_migrations` table.

| File | Owner | Purpose |
|---|---|---|
| `0001_tenants.sql` | WS-301 substrate | tenants table + shared `almighty_set_updated_at` trigger fn |
| `0002_scenarios.sql` | WS-301 substrate | scenarios table including `current_turn` and `turn_state` |
| `0003_entities.sql` | WS-101 lift | entities DDL — copied verbatim from `kernel/schema/entities.sql` |
| `0004_events.sql` | WS-101 lift | events DDL — copied verbatim from `kernel/schema/events.sql` |
| `0005_turn_snapshots.sql` | **WS-302** | one row per closed turn, capturing entities + last-N events as JSONB |

WS-301 may swap this minimal runner for `node-pg-migrate` when it lands
its migrations PR; the SQL files themselves are framework-agnostic.

## Turn advancement workflow (WS-302)

```
POST /tenants/:id/scenarios/:sid/turns/advance
  Authorization: Bearer <white-cell JWT>

200 OK
{
  "tenantId":      "<uuid>",
  "scenarioId":    "<uuid>",
  "closedTurn":    <int>,
  "newTurn":       <int>,
  "snapshotId":    "<uuid>",
  "agentRuntimeMs": <int>
}
```

Internal steps in `src/turn-controller/service.ts`:

1. **Lock** — `SELECT … FOR UPDATE` on the scenario row inside a transaction;
   set `turn_state = 'advancing'`. If already `advancing`, return **409**.
2. **Agent runtime** — `runBetweenTurnAgents()` — *stubbed (WS-401)*;
   sleeps 100 ms, returns success.
3. **Override gateway** — `applyOverrides()` — *stubbed (WS-303)*; no-op.
4. **Snapshot** — read all entities + last 1 000 events for the closing
   turn; insert a `turn_snapshots` row with `snapshot_json`.
5. **Open next turn** — `current_turn += 1`, `turn_state = 'open'`.
   Steps 4 + 5 commit atomically.
6. **Notify** — `publishTurnState()` — *stubbed (WS-304)*; payload built
   so the live publish is a one-line swap.

If the flow crashes after step 1, the catch block reverts
`turn_state` from `advancing` to `open` so retries aren't blocked.

## Local development

```bash
# 1. Spin up Postgres
docker run --rm -d --name almighty-cp-pg \
  -e POSTGRES_PASSWORD=dev -p 5433:5432 postgres:16

# 2. Configure
cp .env.example .env
# edit .env if you want different host/port

# 3. Install + migrate + run
npm install
DATABASE_URL=postgres://postgres:dev@localhost:5433/postgres npm run migrate
DATABASE_URL=postgres://postgres:dev@localhost:5433/postgres \
  JWT_SECRET=dev-secret \
  npm run dev
```

Health check:

```bash
curl localhost:8080/healthz
```

## Tests

```bash
npm test
```

Vitest's `globalSetup` (`tests/setup.ts`) auto-spins a `postgres:16`
docker container, applies migrations, and tears it down at the end.

Override defaults via env:

| Var | Default | Effect |
|---|---|---|
| `PG_TEST_PORT` | `55434` | Host port for the test container. |
| `TEST_DATABASE_URL` | derived | Override entirely. |
| `DOCKER_TEST_DB` | (unset) | `skip` to bypass docker (assumes a DB is reachable at `TEST_DATABASE_URL`). `keep` to leave the container running after tests. |

### What the tests cover

`tests/turn-controller.test.ts` (WS-302 DoD):

- Stubbed end-to-end advance from turn 0 → 1 → 2 → 3.
- Snapshot row exists per closed turn, ordered correctly.
- Snapshot JSON includes the seeded entity and the seeded event for the
  closing turn.
- 409 on advance when scenario is already `advancing`.
- 404 on unknown scenario.

`tests/auth.test.ts` (WS-302 DoD):

- `blue` / `red` / `observer` JWTs all return 403.
- Missing bearer token returns 401.
- Malformed token returns 401.
- JWT `tenant_id` ≠ URL `tenant_id` returns 403.

## Known gaps (deferred)

- **WS-301 CRUD endpoints.** This service has the database substrate and
  auth in place but does not yet expose `POST /tenants`, `GET
  /tenants/:id`, etc. Tenants and scenarios in the test suite are seeded
  via direct SQL `INSERT` for now.
- **Real agent runtime call** — `src/stubs/agent-runtime.ts` carries
  `// TODO WS-401`.
- **Real override gateway call** — `src/stubs/override-gateway.ts`
  carries `// TODO WS-303`.
- **Real WebSocket publish** — `src/stubs/websocket-fanout.ts` carries
  the call site but only logs.
- **Snapshot retention.** v1 keeps every snapshot indefinitely, by design.
  Branching / rollback / scenario forks are Phase 6+ work and will
  introduce a copy-on-write layer.
- **Migration runner.** The minimal `src/db/migrate.ts` is a placeholder.
  WS-301 may upgrade to `node-pg-migrate` when it lands.

## References

- WS-302 issue: #18
- WS-301 issue: #17
- Schema: [`docs/schema/entity-event.md`](../../docs/schema/entity-event.md)
- Glossary — override scopes, white cell: [`docs/glossary.md`](../../docs/glossary.md)
- Implementation gotchas: [`docs/better-late-than-never.md`](../../docs/better-late-than-never.md)
