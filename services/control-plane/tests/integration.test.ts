import { afterAll, beforeAll, beforeEach, describe, expect, it } from "vitest";
import migrationRunner from "node-pg-migrate";
import path from "node:path";
import url from "node:url";
import type { FastifyInstance } from "fastify";
import { buildApp } from "../src/app.js";
import { createPool, type Pool } from "../src/db.js";
import type { CellRole } from "../src/types.js";

const __dirname = path.dirname(url.fileURLToPath(import.meta.url));

const TEST_DATABASE_URL =
  process.env.TEST_DATABASE_URL ?? "postgres://almighty:almighty@localhost:5432/almighty_test";
const JWT_SECRET = "test-secret-".padEnd(40, "x");

const TENANT_A = "11111111-1111-4111-8111-111111111111";
const TENANT_B = "22222222-2222-4222-8222-222222222222";

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
  await pool.query("TRUNCATE events, entities, scenarios, tenants RESTART IDENTITY CASCADE");
});

async function seedTenant(id: string, name: string): Promise<void> {
  await pool.query("INSERT INTO tenants (tenant_id, display_name) VALUES ($1, $2)", [id, name]);
}

describe("auth", () => {
  it("rejects requests without a bearer token", async () => {
    const res = await app.inject({ method: "GET", url: "/tenants" });
    expect(res.statusCode).toBe(401);
  });

  it("rejects malformed JWTs", async () => {
    const res = await app.inject({
      method: "GET",
      url: "/tenants",
      headers: { authorization: "Bearer not-a-jwt" },
    });
    expect(res.statusCode).toBe(401);
  });
});

describe("POST /tenants — white cell can create, others cannot", () => {
  it("white cell creates a tenant", async () => {
    const res = await app.inject({
      method: "POST",
      url: "/tenants",
      headers: auth({ tenant_id: TENANT_A, cell_role: "white" }),
      payload: { display_name: "Acme" },
    });
    expect(res.statusCode).toBe(201);
    expect(res.json()).toMatchObject({ display_name: "Acme", status: "active" });
  });

  it.each(["blue", "red", "observer"] as const)("rejects POST /tenants from %s", async (role) => {
    const res = await app.inject({
      method: "POST",
      url: "/tenants",
      headers: auth({ tenant_id: TENANT_A, cell_role: role }),
      payload: { display_name: "Should-not-create" },
    });
    expect(res.statusCode).toBe(403);
  });
});

describe("cross-tenant isolation", () => {
  beforeEach(async () => {
    await seedTenant(TENANT_A, "Tenant A");
    await seedTenant(TENANT_B, "Tenant B");
  });

  it("GET /tenants returns only the caller's own tenant", async () => {
    const res = await app.inject({
      method: "GET",
      url: "/tenants",
      headers: auth({ tenant_id: TENANT_A, cell_role: "white" }),
    });
    expect(res.statusCode).toBe(200);
    const { tenants } = res.json();
    expect(tenants).toHaveLength(1);
    expect(tenants[0].tenant_id).toBe(TENANT_A);
  });

  it("GET /tenants/:other-tenant-id is denied", async () => {
    const res = await app.inject({
      method: "GET",
      url: `/tenants/${TENANT_B}`,
      headers: auth({ tenant_id: TENANT_A, cell_role: "white" }),
    });
    expect(res.statusCode).toBe(403);
  });

  it("PATCH /tenants/:other-tenant-id is denied", async () => {
    const res = await app.inject({
      method: "PATCH",
      url: `/tenants/${TENANT_B}`,
      headers: auth({ tenant_id: TENANT_A, cell_role: "white" }),
      payload: { display_name: "hacker" },
    });
    expect(res.statusCode).toBe(403);
  });

  it("scenarios in tenant B are not visible to tenant A", async () => {
    const created = await app.inject({
      method: "POST",
      url: `/tenants/${TENANT_B}/scenarios`,
      headers: auth({ tenant_id: TENANT_B, cell_role: "white" }),
      payload: { display_name: "B's scenario" },
    });
    expect(created.statusCode).toBe(201);
    const sid = created.json().scenario_id;

    const cross = await app.inject({
      method: "GET",
      url: `/tenants/${TENANT_B}/scenarios/${sid}`,
      headers: auth({ tenant_id: TENANT_A, cell_role: "white" }),
    });
    expect(cross.statusCode).toBe(403);
  });
});

describe("scenarios cell-role matrix (within own tenant)", () => {
  let scenarioId: string;

  beforeEach(async () => {
    await seedTenant(TENANT_A, "Tenant A");
    const created = await app.inject({
      method: "POST",
      url: `/tenants/${TENANT_A}/scenarios`,
      headers: auth({ tenant_id: TENANT_A, cell_role: "white" }),
      payload: { display_name: "Test scenario" },
    });
    scenarioId = created.json().scenario_id;
  });

  it.each(["white", "blue", "red", "observer"] as const)(
    "%s can read scenario list",
    async (role) => {
      const res = await app.inject({
        method: "GET",
        url: `/tenants/${TENANT_A}/scenarios`,
        headers: auth({ tenant_id: TENANT_A, cell_role: role }),
      });
      expect(res.statusCode).toBe(200);
      expect(res.json().scenarios).toHaveLength(1);
    },
  );

  it.each(["white", "blue", "red", "observer"] as const)(
    "%s can read individual scenario",
    async (role) => {
      const res = await app.inject({
        method: "GET",
        url: `/tenants/${TENANT_A}/scenarios/${scenarioId}`,
        headers: auth({ tenant_id: TENANT_A, cell_role: role }),
      });
      expect(res.statusCode).toBe(200);
    },
  );

  it.each(["blue", "red", "observer"] as const)("%s cannot create scenarios", async (role) => {
    const res = await app.inject({
      method: "POST",
      url: `/tenants/${TENANT_A}/scenarios`,
      headers: auth({ tenant_id: TENANT_A, cell_role: role }),
      payload: { display_name: "Sneaky" },
    });
    expect(res.statusCode).toBe(403);
  });

  it.each(["blue", "red", "observer"] as const)("%s cannot patch scenarios", async (role) => {
    const res = await app.inject({
      method: "PATCH",
      url: `/tenants/${TENANT_A}/scenarios/${scenarioId}`,
      headers: auth({ tenant_id: TENANT_A, cell_role: role }),
      payload: { display_name: "renamed" },
    });
    expect(res.statusCode).toBe(403);
  });

  it.each(["blue", "red", "observer"] as const)("%s cannot delete scenarios", async (role) => {
    const res = await app.inject({
      method: "DELETE",
      url: `/tenants/${TENANT_A}/scenarios/${scenarioId}`,
      headers: auth({ tenant_id: TENANT_A, cell_role: role }),
    });
    expect(res.statusCode).toBe(403);
  });

  it("white cell can patch and soft-delete", async () => {
    const patched = await app.inject({
      method: "PATCH",
      url: `/tenants/${TENANT_A}/scenarios/${scenarioId}`,
      headers: auth({ tenant_id: TENANT_A, cell_role: "white" }),
      payload: { display_name: "renamed", status: "active" },
    });
    expect(patched.statusCode).toBe(200);
    expect(patched.json()).toMatchObject({ display_name: "renamed", status: "active" });

    const deleted = await app.inject({
      method: "DELETE",
      url: `/tenants/${TENANT_A}/scenarios/${scenarioId}`,
      headers: auth({ tenant_id: TENANT_A, cell_role: "white" }),
    });
    expect(deleted.statusCode).toBe(200);
    expect(deleted.json().status).toBe("archived");

    const list = await app.inject({
      method: "GET",
      url: `/tenants/${TENANT_A}/scenarios`,
      headers: auth({ tenant_id: TENANT_A, cell_role: "white" }),
    });
    expect(list.json().scenarios).toHaveLength(0);
  });
});

describe("tenant lifecycle", () => {
  it("PATCH /tenants/:id updates display_name (white only)", async () => {
    await seedTenant(TENANT_A, "Original");
    const res = await app.inject({
      method: "PATCH",
      url: `/tenants/${TENANT_A}`,
      headers: auth({ tenant_id: TENANT_A, cell_role: "white" }),
      payload: { display_name: "Updated" },
    });
    expect(res.statusCode).toBe(200);
    expect(res.json().display_name).toBe("Updated");
  });

  it("DELETE /tenants/:id soft-deletes (status=archived)", async () => {
    await seedTenant(TENANT_A, "Doomed");
    const res = await app.inject({
      method: "DELETE",
      url: `/tenants/${TENANT_A}`,
      headers: auth({ tenant_id: TENANT_A, cell_role: "white" }),
    });
    expect(res.statusCode).toBe(200);
    expect(res.json().status).toBe("archived");

    const list = await app.inject({
      method: "GET",
      url: "/tenants",
      headers: auth({ tenant_id: TENANT_A, cell_role: "white" }),
    });
    expect(list.json().tenants).toHaveLength(0);
  });
});
