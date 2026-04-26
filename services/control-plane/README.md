# `@almighty/control-plane`

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

Multi-tenant control plane for Almighty. Owns the **tenants** + **scenarios** registry, JWT-based RBAC with cell-role enforcement, and the migration that lays down the WS-101 entity/event tables.

## Stack

- Node 20 + Fastify 5 + TypeScript
- `pg` for Postgres access; `node-pg-migrate` for migrations
- `@fastify/jwt` for HS256 JWT verification
- Zod for request body / query / params validation
- Vitest for integration tests (single forked process; tests share one DB)

## Endpoints

| Method | Path | Allowed cell roles | Notes |
|---|---|---|---|
| POST | `/tenants` | white | Create new tenant. Privileged in v1; see "Open question" below. |
| GET | `/tenants` | all | Returns only the caller's own tenant in v1. |
| GET | `/tenants/:id` | all (own tenant) | URL `:id` must equal JWT `tenant_id`. |
| PATCH | `/tenants/:id` | white (own tenant) | Update `display_name`. |
| DELETE | `/tenants/:id` | white (own tenant) | Soft-delete (`status='archived'`). |
| POST | `/tenants/:id/scenarios` | white (own tenant) | Create scenario. |
| GET | `/tenants/:id/scenarios` | all (own tenant) | List active scenarios. |
| GET | `/tenants/:id/scenarios/:sid` | all (own tenant) | Read scenario. |
| PATCH | `/tenants/:id/scenarios/:sid` | white (own tenant) | Update `display_name` / `description` / `status`. |
| DELETE | `/tenants/:id/scenarios/:sid` | white (own tenant) | Soft-delete. |
| POST | `/tenants/:id/scenarios/:sid/turns/advance` | white (own tenant) | WS-302. Advance turn; 409 on conflict, 404 on unknown scenario. |
| POST | `/tenants/:id/scenarios/:sid/overrides` | white (own tenant) | WS-303. Author override policy. |
| GET | `/tenants/:id/scenarios/:sid/overrides` | all (own tenant) | WS-303. List active policies. |
| DELETE | `/tenants/:id/scenarios/:sid/overrides/:oid` | white (own tenant) | WS-303. Revoke (soft; sets `status='revoked'`). |
| POST | `/tenants/:id/scenarios/:sid/events/:eid/decision` | white (own tenant) | WS-303. Manual review decision. |
| GET | `/healthz` | none (open) | Liveness probe. |

**Cross-tenant access is impossible by construction**: the URL `:id` is checked against the JWT's `tenant_id` on every tenant-scoped endpoint, and tenant lists are filtered by JWT `tenant_id`. Cross-tenant requests return `403`.

## JWT shape

Symmetric HS256, signed with `JWT_SECRET`. Claims:

```jsonc
{
  "tenant_id": "<uuid>",                        // binds the request to one tenant
  "cell_role": "white" | "blue" | "red" | "observer",
  "sub": "<optional user id>"
}
```

Production switch to RS256 + JWKS is a config change in `app.ts` (swap `@fastify/jwt` options) — no route or RBAC changes needed.

## DB

Migrations under `migrations/`:

1. **`*_initial-schema.sql`** — applies the WS-101 entity/event DDL (the source-of-truth doc lives at `docs/schema/entity-event.md`; the unrun stub lives at `kernel/schema/entities.sql` + `events.sql`; this migration is the runtime applier).
2. **`*_tenants-scenarios.sql`** — adds `tenants` + `scenarios` tables, both with soft-delete via a `status` enum.
3. **`*_turn-snapshots.sql`** — WS-302. Adds `current_turn` + `turn_state` columns to `scenarios` and the `turn_snapshots` table.
4. **`*_override-policies.sql`** — WS-303. Adds `override_policies` (authored rules) and `override_decisions` (append-only audit log of every gateway firing).

Per-tenant DB isolation (one Postgres database per tenant, à la WS-004) is **not** in scope here; v1 uses a single shared DB with namespace-checked queries. The WS-004 Terraform module remains the production path.

## Run locally

```bash
# 1. Bring up Postgres + the test sibling DB (idempotent).
docker compose up -d postgres

# 2. Install + configure.
pnpm install
cp .env.example .env

# 3. Apply migrations against the dev DB.
pnpm migrate

# 4. Start the dev server.
pnpm dev
# control-plane listening on 0.0.0.0:4000
```

Health check: `curl http://localhost:4000/healthz` → `{"ok":true}`.

## Generating a dev JWT

For ad-hoc local testing (curl, Postman, Insomnia):

```bash
node -e "console.log(require('jsonwebtoken').sign({ tenant_id: '11111111-1111-4111-8111-111111111111', cell_role: 'white' }, process.env.JWT_SECRET))"
```

…then `curl -H "Authorization: Bearer <token>" http://localhost:4000/tenants`.

## Tests

Integration tests run against `TEST_DATABASE_URL` (defaults to the `almighty_test` DB created by `docker-entrypoint`). Each test truncates `events`, `entities`, `scenarios`, `tenants` (CASCADE) before running.

```bash
pnpm migrate:test    # apply migrations to the test DB once
pnpm test            # run integration tests
```

Coverage:
- Auth: 401 on missing / malformed JWT.
- POST `/tenants` cell-role gating (white only).
- Cross-tenant denial: list filtering, GET / PATCH / DELETE on other tenant's IDs, scenario reads from foreign tenant.
- Scenarios cell-role matrix: read for all roles, write only for white.
- Lifecycle: PATCH + soft-delete on tenants and scenarios.

## WS-303 override gateway

The override gateway gates agent-emitted events before they commit to the DAG. Three policy scopes — `per-event` (single event id), `per-agent-per-turn` (entity acting in a specific turn), `per-turn` (blanket rule for a turn) — and three actions: `auto-approve`, `auto-block`, `review`.

### Composability

Strict priority: **per-event > per-agent-per-turn > per-turn > default-review**. The first matching active policy wins. When no policy applies, the default is `review` — the event holds in `review-pending` until a white cell operator posts a manual decision via `POST /events/:eid/decision`.

### TTL

A policy is valid in turn `T` iff `created_in_turn ≤ T ≤ created_in_turn + ttl_turns`. `ttl_turns = 0` means "single-turn validity" (the turn it was authored in).

### Audit

Every evaluation fires an `override_decisions` row, regardless of outcome. The default-review path also logs. Manual decisions append a separate row referencing the same `event_id`. AAR (WS-506) joins this against `events` on `(tenant_id, scenario_id, event_id)` for replay.

### Turn-controller integration

The WS-302 turn controller calls `applyOverrides(pool, …)` from `src/override-gateway.ts` as step 3 of turn-advance. v1 returns `processedEvents = 0` because there is no agent commit queue yet — once WS-401 (agent runtime) lands, this is where queue-drain + per-event evaluation will hook in.

## Open questions

- **POST `/tenants` permission model.** v1 lets any `cell_role: white` JWT create new tenants. Production needs a separate `admin` / `system` role (or an out-of-band tenant-provisioning path) so a white cell in tenant A can't unilaterally create tenant B. Tracked for the WS-301 production hardening pass.
- **Tenant directory.** GET `/tenants` returns only the caller's own tenant in v1. A multi-tenant admin console would need a cross-tenant directory endpoint behind the same admin role above.
- **Per-tenant DB isolation.** Single shared DB in v1; WS-004's Terraform module describes the per-tenant RDS shape but isn't wired here. Switch is a connection-string-per-tenant change in `db.ts`.
