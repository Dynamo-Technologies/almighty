/**
 * Test helpers: minted JWTs, scenario fixtures, etc.
 */

import { SignJWT } from "jose";
import pg from "pg";
import { v4 as uuidv4 } from "uuid";
import type { CellRole } from "../src/auth/jwt.ts";

export const TEST_JWT_SECRET = "test-secret-for-vitest-only";

export async function mintJwt(
  claims: { sub?: string; tenantId: string; cellRole: CellRole },
  options: { expiresIn?: string } = {},
): Promise<string> {
  const key = new TextEncoder().encode(TEST_JWT_SECRET);
  return new SignJWT({
    tenant_id: claims.tenantId,
    cell_role: claims.cellRole,
  })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(claims.sub ?? "test-user")
    .setIssuedAt()
    .setExpirationTime(options.expiresIn ?? "1h")
    .sign(key);
}

export interface ScenarioFixture {
  tenantId: string;
  scenarioId: string;
}

export async function seedScenario(
  pool: pg.Pool,
  options: {
    displayName?: string;
    initialTurn?: number;
    initialState?: "open" | "advancing" | "closed";
  } = {},
): Promise<ScenarioFixture> {
  const tenantId = uuidv4();
  const scenarioId = uuidv4();

  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    await client.query(
      `INSERT INTO tenants (tenant_id, display_name) VALUES ($1, $2)`,
      [tenantId, `test-tenant-${tenantId.slice(0, 8)}`],
    );
    await client.query(
      `INSERT INTO scenarios
            (scenario_id, tenant_id, display_name, current_turn, turn_state)
        VALUES ($1, $2, $3, $4, $5)`,
      [
        scenarioId,
        tenantId,
        options.displayName ?? `test-scenario-${scenarioId.slice(0, 8)}`,
        options.initialTurn ?? 0,
        options.initialState ?? "open",
      ],
    );
    await client.query("COMMIT");
  } catch (err) {
    await client.query("ROLLBACK");
    throw err;
  } finally {
    client.release();
  }

  return { tenantId, scenarioId };
}

export async function seedEntity(
  pool: pg.Pool,
  fixture: ScenarioFixture,
  overrides: Partial<{
    typeCategory: string;
    typeSubtypeRef: string;
    displayName: string;
    forceAffiliation: string;
    capabilitySetRef: string;
  }> = {},
): Promise<string> {
  const entityId = uuidv4();
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
      $4, $5, $6, $7,
      36.18, -86.78, 165.0,
      304113.21, -5142308.55, 3744298.10,
      0, 0, 0,
      1.0, 0, 0, 0,
      $8
    )`,
    [
      entityId,
      fixture.tenantId,
      fixture.scenarioId,
      overrides.typeCategory ?? "PLATFORM",
      overrides.typeSubtypeRef ?? "notional.test.unit",
      overrides.displayName ?? "TEST-1",
      overrides.forceAffiliation ?? "BLUE",
      overrides.capabilitySetRef ?? "us-bct@1",
    ],
  );
  return entityId;
}

export async function seedEvent(
  pool: pg.Pool,
  fixture: ScenarioFixture,
  source: { officerType: string; entityId: string; turn: number; verb: string },
): Promise<string> {
  const eventId = uuidv4();
  await pool.query(
    `INSERT INTO events (
      event_id, tenant_id, scenario_id, turn,
      source_officer_type, source_entity_id, action_verb,
      payload, causal_predecessors, ts
    ) VALUES (
      $1, $2, $3, $4,
      $5, $6, $7,
      '{}'::jsonb, '{}'::uuid[], now()
    )`,
    [
      eventId,
      fixture.tenantId,
      fixture.scenarioId,
      source.turn,
      source.officerType,
      source.entityId,
      source.verb,
    ],
  );
  return eventId;
}
