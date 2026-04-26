# `@almighty/websocket`

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

Tenant-scoped WebSocket fan-out. Maintains four per-tenant channels, gates them by JWT cell-role, and broadcasts messages received via an HTTP `POST /publish` ingress to all matching subscribers — with cross-tenant isolation enforced at every step.

## Stack

- Node 20 + Fastify 5 + TypeScript
- `@fastify/websocket` (wraps the `ws` library) for the WS upgrade
- `@fastify/jwt` for HS256 verification (same `JWT_SECRET` as control-plane so JWTs minted there work here)
- In-process `EventEmitter`-style hub (`src/hub.ts`) for fan-out within one instance. **No Redis in v1** — see "Substitutions" below.
- Vitest for integration tests against a real TCP socket

## Channels and access matrix

| Channel | White | Blue | Red | Observer | Purpose |
|---|:-:|:-:|:-:|:-:|---|
| `events` | ✓ | ✓ | ✓ | ✓ | DAG event broadcast (write-through from kernel) |
| `override_pending` | ✓ | — | — | — | Pauses agent commits until white cell ack |
| `turn_state` | ✓ | ✓ | ✓ | ✓ | Turn lifecycle notifications |
| `czml_packets` | ✓ | ✓ | ✓ | ✓ | Live CZML stream to renderer |

`override_pending` is white-only because review-queue items reveal pending operator decisions that must not leak to blue / red operators (who could otherwise infer the white cell's intent before adjudication completes).

## Cross-tenant isolation

Two enforcement points, both source-of-truth `tenant_id` from the verified JWT:

1. **WebSocket connections** are bucketed into `connectionsByTenant.get(jwt.tenant_id)`. `Hub.publish(tenantId, ...)` only iterates the bucket for that tenant.
2. **`POST /publish`** asserts `body.tenant_id === jwt.tenant_id` and returns `403` otherwise.

Plus the standard JWT-required wall on every endpoint.

## Wire protocol

### Client → Server (over WebSocket)

```jsonc
{ "action": "subscribe",   "channel": "events" }
{ "action": "unsubscribe", "channel": "events" }
{ "action": "ping" }
```

### Server → Client (over WebSocket)

```jsonc
{ "type": "subscribed",   "channel": "events" }
{ "type": "unsubscribed", "channel": "events" }
{ "type": "pong" }
{ "type": "error",   "reason": "..." }
{ "type": "message", "channel": "events", "tenant_id": "<uuid>", "payload": <any> }
```

### Server → Server (HTTP `POST /publish`)

Auth: `Authorization: Bearer <jwt>`, `cell_role` must be `white`.

```jsonc
// body
{ "tenant_id": "<uuid>", "channel": "events", "payload": { /* anything */ } }
// 202 response
{ "delivered": 7, "dropped": 0 }
```

## Connection auth

JWT is read from one of:

1. The `Sec-WebSocket-Protocol` header (browsers pass this as the second arg to `new WebSocket(url, protocols)`).
2. The `?token=<jwt>` query param (CLI / non-browser clients).

If neither is present or the token doesn't verify, the server sends an `error` frame and closes with code `1008` (policy violation).

## Backpressure

Per-connection: `socket.bufferedAmount > MAX_BUFFERED_BYTES` (10 MB default) → drop the *new* message rather than letting the buffer grow unboundedly. The WebSocket protocol doesn't permit unqueueing frames already in the kernel buffer, so "drop-oldest" in the spec sense maps to "drop-newest-on-overflow" in implementation; either choice is a v1 policy and easily switched. Drops are counted in the hub metrics surfaced at `GET /healthz`.

## Run locally

```bash
pnpm install
cp .env.example .env
# JWT_SECRET MUST match the control-plane secret if you want kernel-issued
# JWTs to verify here.
pnpm dev
# websocket listening on 0.0.0.0:4001
```

Quick smoke:

```bash
# Sign a dev JWT
TOKEN=$(node -e "console.log(require('jsonwebtoken').sign({ tenant_id: '11111111-1111-4111-8111-111111111111', cell_role: 'white' }, process.env.JWT_SECRET))")

# Connect (npm install -g wscat first)
wscat -c "ws://localhost:4001/ws?token=$TOKEN"
> {"action":"subscribe","channel":"events"}
< {"type":"subscribed","channel":"events"}

# In another shell, publish
curl -X POST http://localhost:4001/publish \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"11111111-1111-4111-8111-111111111111","channel":"events","payload":{"hello":"world"}}'
# {"delivered":1,"dropped":0}
```

## Tests

```bash
pnpm test
```

Coverage:
- WS auth: rejects missing / invalid token, accepts valid.
- Channel role gating: white can subscribe to all four; blue/red/observer rejected from `override_pending`; everyone admitted to the rest.
- HTTP publish: 401 unauth, 403 non-white role, 403 cross-tenant body, 202 on happy path with delivery confirmation.
- Selectivity: a connection that subscribed only to `turn_state` does not receive `events`.
- **Cross-tenant load isolation**: 4 tenants × 8 connections × 25 publishes per tenant on `events` (200 messages per tenant). Asserts each tenant receives exactly its own 200 messages and zero foreign messages.

The integration suite uses a real TCP socket (Fastify's `app.inject()` doesn't speak WebSocket upgrades), so each test opens / closes real `ws` clients against `127.0.0.1:0`.

## Substitutions from the WS-304 spec

The spec calls for `Redis pub/sub for fan-out between instances`. v1 ships an in-process `EventEmitter`-style hub instead. Justification:

- The hackathon target deploys a single instance per tenant; horizontal scaling is not in v1 scope.
- The `Hub` interface is the only fan-out boundary in the codebase. Swapping its `publish` / `register` to delegate to a Redis adapter is a self-contained change that doesn't touch the routes.
- Redis adds a second piece of infrastructure to dev workflow (Docker container, client library, lifecycle) for zero v1 benefit.

The spec's full stress-test scope (`p95 latency < 200 ms within tenant`, `RSS stable over 5 min`) is similarly deferred — they're scaling assertions whose value lands when we actually scale. The cross-tenant isolation portion of the stress test (the security-critical part) is present in the test suite.

## Open questions

- **Publish authorization granularity.** v1 lets any white-cell JWT publish to its own tenant. Production likely wants a separate "service" claim (e.g., `actor: "kernel"`) so a stolen white-cell operator JWT can't impersonate the kernel. Track with the same WS-301 production-hardening pass.
- **Backpressure policy.** Drop-newest-on-overflow vs close-the-connection vs slow-down-the-publisher. v1 picks the simplest; revisit when a real client misbehaves.
- **Connection limits per tenant.** Unbounded in v1. A misconfigured renderer could exhaust file descriptors.
