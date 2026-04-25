/**
 * WS-302 — turn controller integration tests.
 *
 * Confirms:
 * - Stubbed end-to-end advance from turn 0 → 1 → 2 → 3.
 * - Snapshot row exists for every turn that closed, ordered correctly.
 * - 409 on double-advance while turn_state='advancing'.
 * - 404 on unknown scenario.
 */

import { afterAll, beforeAll, describe, expect, test } from "vitest";
import pg from "pg";
import { buildApp } from "../src/server.ts";
import { closePool, getPool } from "../src/db/pool.ts";
import {
  TEST_JWT_SECRET,
  mintJwt,
  seedEntity,
  seedEvent,
  seedScenario,
} from "./helpers.ts";

const dbUrl = process.env.TEST_DATABASE_URL!;

describe("WS-302 turn-advance flow", () => {
  let app: ReturnType<typeof buildApp>;
  let pool: pg.Pool;

  beforeAll(async () => {
    app = buildApp({ jwtSecret: TEST_JWT_SECRET, databaseUrl: dbUrl, logLevel: "silent" });
    await app.ready();
    pool = getPool(dbUrl);
  });

  afterAll(async () => {
    await app.close();
    await closePool();
  });

  test("advance turn 0 -> 1 -> 2 -> 3 with snapshot per turn", async () => {
    const fixture = await seedScenario(pool);
    const token = await mintJwt({ tenantId: fixture.tenantId, cellRole: "white" });

    // Seed an entity so the snapshot has something non-trivial in it.
    const entityId = await seedEntity(pool, fixture);

    for (let expectedClosing = 0; expectedClosing < 3; expectedClosing++) {
      // Seed one event for the closing turn so the snapshot's events array is non-empty.
      await seedEvent(pool, fixture, {
        officerType: "COMMANDER",
        entityId,
        turn: expectedClosing,
        verb: "issue_order",
      });

      const response = await app.inject({
        method: "POST",
        url: `/tenants/${fixture.tenantId}/scenarios/${fixture.scenarioId}/turns/advance`,
        headers: { authorization: `Bearer ${token}` },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      expect(body.closedTurn).toBe(expectedClosing);
      expect(body.newTurn).toBe(expectedClosing + 1);
      expect(body.snapshotId).toBeTruthy();
      expect(body.agentRuntimeMs).toBeGreaterThanOrEqual(100);

      const scenarioRow = await pool.query<{
        current_turn: number;
        turn_state: string;
      }>(
        "SELECT current_turn, turn_state FROM scenarios WHERE scenario_id = $1",
        [fixture.scenarioId],
      );
      expect(scenarioRow.rows[0]!.current_turn).toBe(expectedClosing + 1);
      expect(scenarioRow.rows[0]!.turn_state).toBe("open");
    }

    // Confirm 3 snapshot rows, one per closed turn.
    const snapshots = await pool.query<{ turn: number }>(
      `SELECT turn FROM turn_snapshots
        WHERE tenant_id = $1 AND scenario_id = $2
        ORDER BY turn ASC`,
      [fixture.tenantId, fixture.scenarioId],
    );
    expect(snapshots.rows.map((r) => r.turn)).toEqual([0, 1, 2]);

    // Snapshot for turn 1 should include the entity row and the event for turn 1.
    const turnOneSnap = await pool.query<{ snapshot_json: { entities: unknown[]; events: unknown[] } }>(
      `SELECT snapshot_json FROM turn_snapshots
        WHERE tenant_id = $1 AND scenario_id = $2 AND turn = $3`,
      [fixture.tenantId, fixture.scenarioId, 1],
    );
    expect(turnOneSnap.rows[0]!.snapshot_json.entities.length).toBe(1);
    expect(turnOneSnap.rows[0]!.snapshot_json.events.length).toBe(1);
  });

  test("returns 409 when scenario already advancing", async () => {
    const fixture = await seedScenario(pool, { initialState: "advancing" });
    const token = await mintJwt({ tenantId: fixture.tenantId, cellRole: "white" });

    const response = await app.inject({
      method: "POST",
      url: `/tenants/${fixture.tenantId}/scenarios/${fixture.scenarioId}/turns/advance`,
      headers: { authorization: `Bearer ${token}` },
    });
    expect(response.statusCode).toBe(409);
  });

  test("returns 404 on unknown scenario", async () => {
    const fixture = await seedScenario(pool);
    const token = await mintJwt({ tenantId: fixture.tenantId, cellRole: "white" });
    const bogus = "00000000-0000-0000-0000-000000000000";

    const response = await app.inject({
      method: "POST",
      url: `/tenants/${fixture.tenantId}/scenarios/${bogus}/turns/advance`,
      headers: { authorization: `Bearer ${token}` },
    });
    expect(response.statusCode).toBe(404);
  });
});
