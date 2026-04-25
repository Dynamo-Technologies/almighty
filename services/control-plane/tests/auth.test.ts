/**
 * Auth contract tests for /turns/advance.
 *
 * - blue / red / observer JWTs return 403.
 * - missing / malformed token returns 401.
 * - JWT tenant_id mismatch with URL returns 403.
 */

import { afterAll, beforeAll, describe, expect, test } from "vitest";
import { buildApp } from "../src/server.ts";
import { closePool, getPool } from "../src/db/pool.ts";
import {
  TEST_JWT_SECRET,
  mintJwt,
  seedScenario,
} from "./helpers.ts";

const dbUrl = process.env.TEST_DATABASE_URL!;

describe("WS-302 auth", () => {
  let app: ReturnType<typeof buildApp>;

  beforeAll(async () => {
    app = buildApp({ jwtSecret: TEST_JWT_SECRET, databaseUrl: dbUrl, logLevel: "silent" });
    await app.ready();
  });

  afterAll(async () => {
    await app.close();
    await closePool();
  });

  test.each(["blue", "red", "observer"] as const)(
    "%s cell_role is rejected with 403",
    async (cellRole) => {
      const pool = getPool(dbUrl);
      const fixture = await seedScenario(pool);
      const token = await mintJwt({ tenantId: fixture.tenantId, cellRole });

      const response = await app.inject({
        method: "POST",
        url: `/tenants/${fixture.tenantId}/scenarios/${fixture.scenarioId}/turns/advance`,
        headers: { authorization: `Bearer ${token}` },
      });
      expect(response.statusCode).toBe(403);
    },
  );

  test("missing bearer token returns 401", async () => {
    const pool = getPool(dbUrl);
    const fixture = await seedScenario(pool);

    const response = await app.inject({
      method: "POST",
      url: `/tenants/${fixture.tenantId}/scenarios/${fixture.scenarioId}/turns/advance`,
    });
    expect(response.statusCode).toBe(401);
  });

  test("malformed token returns 401", async () => {
    const pool = getPool(dbUrl);
    const fixture = await seedScenario(pool);

    const response = await app.inject({
      method: "POST",
      url: `/tenants/${fixture.tenantId}/scenarios/${fixture.scenarioId}/turns/advance`,
      headers: { authorization: "Bearer not-a-real-jwt" },
    });
    expect(response.statusCode).toBe(401);
  });

  test("jwt tenant_id != url tenant_id returns 403", async () => {
    const pool = getPool(dbUrl);
    const fixture = await seedScenario(pool);
    // Mint a white-cell token for a *different* tenant.
    const wrongTenant = "11111111-1111-1111-1111-111111111111";
    const token = await mintJwt({ tenantId: wrongTenant, cellRole: "white" });

    const response = await app.inject({
      method: "POST",
      url: `/tenants/${fixture.tenantId}/scenarios/${fixture.scenarioId}/turns/advance`,
      headers: { authorization: `Bearer ${token}` },
    });
    expect(response.statusCode).toBe(403);
  });
});
