/**
 * WS-302 turn controller integration tests.
 *
 * Mirrors tests/integration.test.ts setup style:
 *   - Real Postgres at TEST_DATABASE_URL.
 *   - migrationRunner up.
 *   - One buildApp per file.
 *   - TRUNCATE between tests (CASCADE through events/entities/scenarios/tenants/turn_snapshots).
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

const __dirname = path.dirname(url.fileURLToPath(import.meta.url));

const TEST_DATABASE_URL =
  process.env.TEST_DATABASE_URL ??
  "postgres://almighty:almighty@localhost:5432/almighty_test";
const JWT_SECRET = "test-secret-".padEnd(40, "x");

const TENANT_A = "11111111-1111-4111-8111-111111111111";

let app: FastifyInstance;
let pool: Pool;
const sign = (claims: { tenant_id: string; cell_role: CellRole }): string =>
  app.jwt.sign(claims);
const auth = (claims: { tenant_id: string; cell_role: CellRole }) => ({
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
    "TRUNCATE turn_snapshots, events, entities, scenarios, tenants RESTART IDENTITY CASCADE",
  );
});

async function seedTenantAndScenario(): Promise<{
  tenantId: string;
  scenarioId: string;
}> {
  await pool.query(
    "INSERT INTO tenants (tenant_id, display_name) VALUES ($1, $2)",
    [TENANT_A, "Tenant A"],
  );
  const created = await app.inject({
    method: "POST",
    url: `/tenants/${TENANT_A}/scenarios`,
    headers: auth({ tenant_id: TENANT_A, cell_role: "white" }),
    payload: { display_name: "WS-302 test scenario" },
  });
  if (created.statusCode !== 201) {
    throw new Error(`scenario seed failed: ${created.statusCode} ${created.body}`);
  }
  return { tenantId: TENANT_A, scenarioId: created.json().scenario_id };
}

async function seedEntity(
  tenantId: string,
  scenarioId: string,
): Promise<string> {
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
): Promise<void> {
  await pool.query(
    `INSERT INTO events (
       event_id, tenant_id, scenario_id, turn,
       source_officer_type, source_entity_id, action_verb,
       payload, causal_predecessors, ts
     ) VALUES (
       $1, $2, $3, $4,
       'COMMANDER', $5, 'issue_order',
       '{}'::jsonb, '{}'::uuid[], now()
     )`,
    [randomUUID(), tenantId, scenarioId, turn, entityId],
  );
}

describe("WS-302 turn-advance flow", () => {
  it("advances turn 0 -> 1 -> 2 -> 3 with a snapshot per closed turn", async () => {
    const { tenantId, scenarioId } = await seedTenantAndScenario();
    const entityId = await seedEntity(tenantId, scenarioId);

    for (let expectedClosing = 0; expectedClosing < 3; expectedClosing++) {
      // Seed one event for the turn that's about to close.
      await seedEvent(tenantId, scenarioId, entityId, expectedClosing);

      const res = await app.inject({
        method: "POST",
        url: `/tenants/${tenantId}/scenarios/${scenarioId}/turns/advance`,
        headers: auth({ tenant_id: tenantId, cell_role: "white" }),
      });

      expect(res.statusCode).toBe(200);
      const body = res.json();
      expect(body.closedTurn).toBe(expectedClosing);
      expect(body.newTurn).toBe(expectedClosing + 1);
      expect(body.snapshotId).toBeTruthy();
      expect(body.agentRuntimeMs).toBeGreaterThanOrEqual(100);

      const scenarioRow = await pool.query<{
        current_turn: number;
        turn_state: string;
      }>(
        "SELECT current_turn, turn_state FROM scenarios WHERE scenario_id = $1",
        [scenarioId],
      );
      expect(scenarioRow.rows[0]!.current_turn).toBe(expectedClosing + 1);
      expect(scenarioRow.rows[0]!.turn_state).toBe("open");
    }

    const snapshots = await pool.query<{ turn: number }>(
      `SELECT turn FROM turn_snapshots
        WHERE tenant_id = $1 AND scenario_id = $2
        ORDER BY turn ASC`,
      [tenantId, scenarioId],
    );
    expect(snapshots.rows.map((r) => r.turn)).toEqual([0, 1, 2]);

    const turnOneSnap = await pool.query<{
      snapshot_json: { entities: unknown[]; events: unknown[] };
    }>(
      `SELECT snapshot_json FROM turn_snapshots
        WHERE tenant_id = $1 AND scenario_id = $2 AND turn = $3`,
      [tenantId, scenarioId, 1],
    );
    expect(turnOneSnap.rows[0]!.snapshot_json.entities).toHaveLength(1);
    expect(turnOneSnap.rows[0]!.snapshot_json.events).toHaveLength(1);
  });

  it("returns 409 when scenario is already advancing", async () => {
    const { tenantId, scenarioId } = await seedTenantAndScenario();
    await pool.query(
      "UPDATE scenarios SET turn_state = 'advancing' WHERE scenario_id = $1",
      [scenarioId],
    );

    const res = await app.inject({
      method: "POST",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/turns/advance`,
      headers: auth({ tenant_id: tenantId, cell_role: "white" }),
    });
    expect(res.statusCode).toBe(409);
  });

  it("returns 404 on unknown scenario", async () => {
    const { tenantId } = await seedTenantAndScenario();
    const bogus = "00000000-0000-4000-8000-000000000000";

    const res = await app.inject({
      method: "POST",
      url: `/tenants/${tenantId}/scenarios/${bogus}/turns/advance`,
      headers: auth({ tenant_id: tenantId, cell_role: "white" }),
    });
    expect(res.statusCode).toBe(404);
  });
});

describe("WS-302 auth gates", () => {
  it.each(["blue", "red", "observer"] as const)(
    "%s cell_role is rejected with 403",
    async (cellRole) => {
      const { tenantId, scenarioId } = await seedTenantAndScenario();
      const res = await app.inject({
        method: "POST",
        url: `/tenants/${tenantId}/scenarios/${scenarioId}/turns/advance`,
        headers: auth({ tenant_id: tenantId, cell_role: cellRole }),
      });
      expect(res.statusCode).toBe(403);
    },
  );

  it("missing bearer token returns 401", async () => {
    const { tenantId, scenarioId } = await seedTenantAndScenario();
    const res = await app.inject({
      method: "POST",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/turns/advance`,
    });
    expect(res.statusCode).toBe(401);
  });

  it("malformed token returns 401", async () => {
    const { tenantId, scenarioId } = await seedTenantAndScenario();
    const res = await app.inject({
      method: "POST",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/turns/advance`,
      headers: { authorization: "Bearer not-a-real-jwt" },
    });
    expect(res.statusCode).toBe(401);
  });

  it("jwt tenant_id != url tenant_id returns 403", async () => {
    const { tenantId, scenarioId } = await seedTenantAndScenario();
    const wrongTenant = "22222222-2222-4222-8222-222222222222";

    const res = await app.inject({
      method: "POST",
      url: `/tenants/${tenantId}/scenarios/${scenarioId}/turns/advance`,
      headers: auth({ tenant_id: wrongTenant, cell_role: "white" }),
    });
    expect(res.statusCode).toBe(403);
  });
});
