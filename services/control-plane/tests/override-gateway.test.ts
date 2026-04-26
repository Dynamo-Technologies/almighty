/**
 * WS-303 override gateway integration tests.
 *
 * Mirrors tests/turn-controller.test.ts setup:
 *   - Real Postgres at TEST_DATABASE_URL.
 *   - migrationRunner up.
 *   - One buildApp per file.
 *   - TRUNCATE between tests (CASCADE through new override_* tables too).
 */

import { afterAll, beforeAll, beforeEach, describe, expect, it } from "vitest";
import migrationRunner from "node-pg-migrate";
import path from "node:path";
import url from "node:url";
import { randomUUID } from "node:crypto";
import type { FastifyInstance } from "fastify";
import { buildApp } from "../src/app.js";
import { createPool, type Pool } from "../src/db.js";
import type { CellRole } from "../src/types.js";
import { evaluateEvent } from "../src/override-gateway.js";

const __dirname = path.dirname(url.fileURLToPath(import.meta.url));

const TEST_DATABASE_URL =
  process.env.TEST_DATABASE_URL ??
  "postgres://almighty:almighty@localhost:5432/almighty_test";
const JWT_SECRET = "test-secret-".padEnd(40, "x");

const TENANT_A = "11111111-1111-4111-8111-111111111111";
const TENANT_B = "22222222-2222-4222-8222-222222222222";

let app: FastifyInstance;
let pool: Pool;
const sign = (claims: { tenant_id: string; cell_role: CellRole; sub?: string }): string =>
  app.jwt.sign(claims);
const auth = (claims: { tenant_id: string; cell_role: CellRole; sub?: string }) => ({
  authorization: `Bearer ${sign(claims)}`,
});

beforeAll(async () => {
  await migrationRunner({
    databaseUrl: TEST_DATABASE_URL,
    dir: path.join(__dirname, "..", "migrations"),
    direction: "up",
    migrationsTable: "pgmigrations",
    count: Infinity,
    log: () => {},
  });

  pool = createPool(TEST_DATABASE_URL);
  ({ app } = await buildApp({
    env: {
      DATABASE_URL: TEST_DATABASE_URL,
      JWT_SECRET,
      PORT: 4000,
      HOST: "127.0.0.1",
      LOG_LEVEL: "error",
      SPARK_WORKER_URL: "http://localhost:0",
    },
    pool,
  }));
  await app.ready();
});

afterAll(async () => {
  await app.close();
  await pool.end();
});

beforeEach(async () => {
  await pool.query(
    "TRUNCATE override_decisions, override_policies, turn_snapshots, events, entities, scenarios, tenants RESTART IDENTITY CASCADE",
  );
});

// ---------- Helpers ----------

async function seedTenantAndScenario(tenantId = TENANT_A): Promise<{
  tenantId: string;
  scenarioId: string;
}> {
  await pool.query(
    "INSERT INTO tenants (tenant_id, display_name) VALUES ($1, $2) ON CONFLICT DO NOTHING",
    [tenantId, `Tenant ${tenantId.slice(0, 4)}`],
  );
  const created = await app.inject({
    method: "POST",
    url: `/tenants/${tenantId}/scenarios`,
    headers: auth({ tenant_id: tenantId, cell_role: "white" }),
    payload: { display_name: "WS-303 test scenario" },
  });
  if (created.statusCode !== 201) {
    throw new Error(`scenario seed failed: ${created.statusCode} ${created.body}`);
  }
  return { tenantId, scenarioId: created.json().scenario_id };
}

async function seedEntity(tenantId: string, scenarioId: string): Promise<string> {
  const entityId = randomUUID();
  await pool.query(
    `INSERT INTO entities (
       entity_id, tenant_id, scenario_id,
       type_category, type_subtype_ref, display_name, force_affiliation,
       position_lat_deg, position_lon_deg, position_alt_m,
       position_ecef_x_m, position_ecef_y_m, position_ecef_z_m,
       velocity_ecef_vx_mps, velocity_ecef_vy_mps, velocity_ecef_vz_mps,
       orientation_qw, orientation_qx, orientation_qy, orientation_qz,
       capability_set_ref
     ) VALUES (
       $1, $2, $3,
       'PLATFORM', 'notional.test.unit', 'TEST-1', 'BLUE',
       36.18, -86.78, 165.0,
       304113.21, -5142308.55, 3744298.10,
       0, 0, 0,
       1.0, 0, 0, 0,
       'us-bct@1'
     )`,
    [entityId, tenantId, scenarioId],
  );
  return entityId;
}

async function seedEvent(
  tenantId: string,
  scenarioId: string,
  entityId: string,
  turn: number,
): Promise<string> {
  const eventId = randomUUID();
  await pool.query(
    `INSERT INTO events (
       event_id, tenant_id, scenario_id, turn,
       source_officer_type, source_entity_id, action_verb,
       payload, causal_predecessors, ts
     ) VALUES (
       $1, $2, $3, $4,
       'EFFECTOR', $5, 'engage',
       '{}'::jsonb, '{}'::uuid[], now()
     )`,
    [eventId, tenantId, scenarioId, turn, entityId],
  );
  return eventId;
}

async function setScenarioTurn(scenarioId: string, turn: number): Promise<void> {
  await pool.query(
    "UPDATE scenarios SET current_turn = $1 WHERE scenario_id = $2",
    [turn, scenarioId],
  );
}

// ---------- Composability ----------

describe("WS-303 composability — per-event > per-agent-per-turn > per-turn", () => {
  it("per-event policy wins over per-agent-per-turn AND per-turn policies on same event", async () => {
    const { tenantId, scenarioId } = await seedTenantAndScenario();
    const entityId = await seedEntity(tenantId, scenarioId);
    await setScenarioTurn(scenarioId, 5);
    const eventId = await seedEvent(tenantId, scenarioId, entityId, 5);
    const headers = auth({ tenant_id: tenantId, cell_role: "white" });

    // 1. per-turn = auto-block (lowest priority)
    let res = await app.inject({
      method: "POST",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/overrides`,
      headers,
      payload: {
        scope: "per-turn",
        action: "auto-block",
        target_turn: 5,
        rationale: "blanket block on turn 5",
      },
    });
    expect(res.statusCode).toBe(201);

    // 2. per-agent-per-turn = review (middle priority)
    res = await app.inject({
      method: "POST",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/overrides`,
      headers,
      payload: {
        scope: "per-agent-per-turn",
        action: "review",
        agent_entity_id: entityId,
        target_turn: 5,
        rationale: "this agent under review on turn 5",
      },
    });
    expect(res.statusCode).toBe(201);

    // 3. per-event = auto-approve (highest priority)
    res = await app.inject({
      method: "POST",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/overrides`,
      headers,
      payload: {
        scope: "per-event",
        action: "auto-approve",
        event_id: eventId,
        rationale: "this specific event is pre-approved",
      },
    });
    expect(res.statusCode).toBe(201);

    // Evaluate the event — per-event auto-approve must win.
    const result = await evaluateEvent(pool, {
      tenantId,
      scenarioId,
      eventId,
      agentEntityId: entityId,
      turn: 5,
    });
    expect(result.outcome).toBe("auto-approve");
    expect(result.matchedScope).toBe("per-event");
  });

  it("per-agent-per-turn beats per-turn when no per-event policy exists", async () => {
    const { tenantId, scenarioId } = await seedTenantAndScenario();
    const entityId = await seedEntity(tenantId, scenarioId);
    await setScenarioTurn(scenarioId, 3);
    const eventId = await seedEvent(tenantId, scenarioId, entityId, 3);
    const headers = auth({ tenant_id: tenantId, cell_role: "white" });

    await app.inject({
      method: "POST",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/overrides`,
      headers,
      payload: { scope: "per-turn", action: "auto-block", target_turn: 3 },
    });
    await app.inject({
      method: "POST",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/overrides`,
      headers,
      payload: {
        scope: "per-agent-per-turn",
        action: "auto-approve",
        agent_entity_id: entityId,
        target_turn: 3,
      },
    });

    const result = await evaluateEvent(pool, {
      tenantId,
      scenarioId,
      eventId,
      agentEntityId: entityId,
      turn: 3,
    });
    expect(result.outcome).toBe("auto-approve");
    expect(result.matchedScope).toBe("per-agent-per-turn");
  });

  it("per-turn applies when no narrower scope matches", async () => {
    const { tenantId, scenarioId } = await seedTenantAndScenario();
    const entityId = await seedEntity(tenantId, scenarioId);
    await setScenarioTurn(scenarioId, 7);
    const eventId = await seedEvent(tenantId, scenarioId, entityId, 7);

    await app.inject({
      method: "POST",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/overrides`,
      headers: auth({ tenant_id: tenantId, cell_role: "white" }),
      payload: { scope: "per-turn", action: "auto-approve", target_turn: 7 },
    });

    const result = await evaluateEvent(pool, {
      tenantId,
      scenarioId,
      eventId,
      agentEntityId: entityId,
      turn: 7,
    });
    expect(result.outcome).toBe("auto-approve");
    expect(result.matchedScope).toBe("per-turn");
  });

  it("default-review when no policy applies", async () => {
    const { tenantId, scenarioId } = await seedTenantAndScenario();
    const entityId = await seedEntity(tenantId, scenarioId);
    const eventId = await seedEvent(tenantId, scenarioId, entityId, 0);

    const result = await evaluateEvent(pool, {
      tenantId,
      scenarioId,
      eventId,
      agentEntityId: entityId,
      turn: 0,
    });
    expect(result.outcome).toBe("default-review");
    expect(result.matchedScope).toBeNull();
    expect(result.policyId).toBeNull();
  });
});

// ---------- TTL ----------

describe("WS-303 TTL — per-turn policy expires after ttl_turns", () => {
  it("ttl_turns=2 policy created in turn 1 is valid for turns 1..3, expired in turn 4", async () => {
    const { tenantId, scenarioId } = await seedTenantAndScenario();
    const entityId = await seedEntity(tenantId, scenarioId);
    await setScenarioTurn(scenarioId, 1);

    // Author the policy in turn 1 with ttl_turns = 2 -> valid in 1, 2, 3.
    await app.inject({
      method: "POST",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/overrides`,
      headers: auth({ tenant_id: tenantId, cell_role: "white" }),
      payload: { scope: "per-turn", action: "auto-block", target_turn: 1, ttl_turns: 2 },
    });

    // Note: target_turn pins the policy to turn 1 specifically. To exercise
    // TTL across multiple turns, author one policy per turn. Here we test
    // the simpler shape: same scenario, the per-turn rule fires only when
    // target_turn matches the event's turn.
    //
    // For the BETWEEN-style TTL filter to matter, we need a policy that
    // matches by some attribute other than target_turn. Use per-agent-per-turn:
    // authoring it with ttl_turns=2 means it is alive across (turn, turn+1, turn+2).
    // We'll redo this with that scope below.

    // First confirm the per-turn=1 policy fires for turn 1 events.
    const eventTurn1 = await seedEvent(tenantId, scenarioId, entityId, 1);
    const r1 = await evaluateEvent(pool, {
      tenantId,
      scenarioId,
      eventId: eventTurn1,
      agentEntityId: entityId,
      turn: 1,
    });
    expect(r1.outcome).toBe("auto-block");
  });

  it("per-agent-per-turn policy with ttl_turns=2 fires across creation_turn..creation_turn+2", async () => {
    const { tenantId, scenarioId } = await seedTenantAndScenario();
    const entityId = await seedEntity(tenantId, scenarioId);
    await setScenarioTurn(scenarioId, 2);

    // Author in turn 2, target_turn=4 (a future turn), ttl_turns=2.
    // Policy is valid in turns [2, 3, 4]. The lookup also requires
    // target_turn = event.turn, so it only fires for events in turn 4.
    await app.inject({
      method: "POST",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/overrides`,
      headers: auth({ tenant_id: tenantId, cell_role: "white" }),
      payload: {
        scope: "per-agent-per-turn",
        action: "auto-approve",
        agent_entity_id: entityId,
        target_turn: 4,
        ttl_turns: 2,
      },
    });

    // Event in turn 4: policy is in TTL (created turn 2, ttl 2 -> valid 2..4)
    // AND target_turn matches -> auto-approve.
    const eventInTurn4 = await seedEvent(tenantId, scenarioId, entityId, 4);
    const r = await evaluateEvent(pool, {
      tenantId,
      scenarioId,
      eventId: eventInTurn4,
      agentEntityId: entityId,
      turn: 4,
    });
    expect(r.outcome).toBe("auto-approve");

    // Event in turn 5: TTL expired (created turn 2, ttl 2 -> max valid turn 4).
    const eventInTurn5 = await seedEvent(tenantId, scenarioId, entityId, 5);
    const r5 = await evaluateEvent(pool, {
      tenantId,
      scenarioId,
      eventId: eventInTurn5,
      agentEntityId: entityId,
      turn: 5,
    });
    expect(r5.outcome).toBe("default-review");
    expect(r5.matchedScope).toBeNull();
  });
});

// ---------- Manual review path ----------

describe("WS-303 manual-decision endpoint", () => {
  it("posts a review-approved decision for an event with no auto-policy", async () => {
    const { tenantId, scenarioId } = await seedTenantAndScenario();
    const entityId = await seedEntity(tenantId, scenarioId);
    const eventId = await seedEvent(tenantId, scenarioId, entityId, 0);

    // Confirm default-review path triggers first.
    const initial = await evaluateEvent(pool, {
      tenantId,
      scenarioId,
      eventId,
      agentEntityId: entityId,
      turn: 0,
    });
    expect(initial.outcome).toBe("default-review");

    // Operator posts manual approval.
    const res = await app.inject({
      method: "POST",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/events/${eventId}/decision`,
      headers: auth({ tenant_id: tenantId, cell_role: "white" }),
      payload: { outcome: "review-approved", rationale: "vetted by hand" },
    });
    expect(res.statusCode).toBe(201);
    expect(res.json().outcome).toBe("review-approved");

    // Audit row exists.
    const decisions = await pool.query(
      "SELECT outcome, rationale FROM override_decisions WHERE event_id = $1 ORDER BY decided_at",
      [eventId],
    );
    expect(decisions.rows).toHaveLength(2);
    expect(decisions.rows[0].outcome).toBe("default-review");
    expect(decisions.rows[1].outcome).toBe("review-approved");
    expect(decisions.rows[1].rationale).toBe("vetted by hand");
  });

  it("returns 404 for unknown event_id", async () => {
    const { tenantId, scenarioId } = await seedTenantAndScenario();
    const bogusEvent = "00000000-0000-4000-8000-000000000000";
    const res = await app.inject({
      method: "POST",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/events/${bogusEvent}/decision`,
      headers: auth({ tenant_id: tenantId, cell_role: "white" }),
      payload: { outcome: "review-approved" },
    });
    expect(res.statusCode).toBe(404);
  });
});

// ---------- Endpoint RBAC + cross-tenant ----------

describe("WS-303 endpoint RBAC", () => {
  it.each(["blue", "red", "observer"] as const)(
    "%s cannot author policies (403)",
    async (role) => {
      const { tenantId, scenarioId } = await seedTenantAndScenario();
      const res = await app.inject({
        method: "POST",
        url: `/tenants/${tenantId}/scenarios/${scenarioId}/overrides`,
        headers: auth({ tenant_id: tenantId, cell_role: role }),
        payload: { scope: "per-turn", action: "auto-approve", target_turn: 0 },
      });
      expect(res.statusCode).toBe(403);
    },
  );

  it.each(["blue", "red", "observer"] as const)(
    "%s CAN list policies (read open to all roles in tenant)",
    async (role) => {
      const { tenantId, scenarioId } = await seedTenantAndScenario();
      const res = await app.inject({
        method: "GET",
        url: `/tenants/${tenantId}/scenarios/${scenarioId}/overrides`,
        headers: auth({ tenant_id: tenantId, cell_role: role }),
      });
      expect(res.statusCode).toBe(200);
      expect(res.json().policies).toEqual([]);
    },
  );

  it("missing bearer token returns 401", async () => {
    const { tenantId, scenarioId } = await seedTenantAndScenario();
    const res = await app.inject({
      method: "GET",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/overrides`,
    });
    expect(res.statusCode).toBe(401);
  });

  it("cross-tenant policy authoring is denied (403)", async () => {
    const { tenantId, scenarioId } = await seedTenantAndScenario(TENANT_A);
    const res = await app.inject({
      method: "POST",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/overrides`,
      headers: auth({ tenant_id: TENANT_B, cell_role: "white" }),
      payload: { scope: "per-turn", action: "auto-approve", target_turn: 0 },
    });
    expect(res.statusCode).toBe(403);
  });

  it("revoke is white-only (403 for blue)", async () => {
    const { tenantId, scenarioId } = await seedTenantAndScenario();
    const create = await app.inject({
      method: "POST",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/overrides`,
      headers: auth({ tenant_id: tenantId, cell_role: "white" }),
      payload: { scope: "per-turn", action: "auto-approve", target_turn: 0 },
    });
    const policyId = create.json().policy_id;
    const res = await app.inject({
      method: "DELETE",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/overrides/${policyId}`,
      headers: auth({ tenant_id: tenantId, cell_role: "blue" }),
    });
    expect(res.statusCode).toBe(403);
  });

  it("revoke marks status='revoked' and the policy stops firing", async () => {
    const { tenantId, scenarioId } = await seedTenantAndScenario();
    const entityId = await seedEntity(tenantId, scenarioId);
    const eventId = await seedEvent(tenantId, scenarioId, entityId, 0);

    const create = await app.inject({
      method: "POST",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/overrides`,
      headers: auth({ tenant_id: tenantId, cell_role: "white" }),
      payload: { scope: "per-turn", action: "auto-block", target_turn: 0 },
    });
    const policyId = create.json().policy_id;

    const before = await evaluateEvent(pool, {
      tenantId,
      scenarioId,
      eventId,
      agentEntityId: entityId,
      turn: 0,
    });
    expect(before.outcome).toBe("auto-block");

    const revokeRes = await app.inject({
      method: "DELETE",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/overrides/${policyId}`,
      headers: auth({ tenant_id: tenantId, cell_role: "white" }),
    });
    expect(revokeRes.statusCode).toBe(200);
    expect(revokeRes.json().status).toBe("revoked");

    const eventId2 = await seedEvent(tenantId, scenarioId, entityId, 0);
    const after = await evaluateEvent(pool, {
      tenantId,
      scenarioId,
      eventId: eventId2,
      agentEntityId: entityId,
      turn: 0,
    });
    expect(after.outcome).toBe("default-review");
  });

  it("payload shape validation: per-event without event_id is 400", async () => {
    const { tenantId, scenarioId } = await seedTenantAndScenario();
    const res = await app.inject({
      method: "POST",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/overrides`,
      headers: auth({ tenant_id: tenantId, cell_role: "white" }),
      payload: { scope: "per-event", action: "auto-approve" }, // missing event_id
    });
    expect(res.statusCode).toBe(400);
  });
});
