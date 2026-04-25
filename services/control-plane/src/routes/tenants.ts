import type { FastifyInstance } from "fastify";
import type { Pool } from "../db.js";
import { requireAuth, requireCellRole, requireOwnTenant } from "../auth.js";
import { CreateTenantBody, TenantIdParams, UpdateTenantBody } from "../types.js";

export async function registerTenantRoutes(app: FastifyInstance, db: Pool): Promise<void> {
  // POST /tenants — create new tenant. Privileged: any cell_role=white can do this in v1.
  // Open question for production: introduce a separate admin/system role.
  app.post("/tenants", { preHandler: [requireAuth, requireCellRole("white")] }, async (req, reply) => {
    const body = CreateTenantBody.parse(req.body);
    const result = await db.query(
      `INSERT INTO tenants (display_name) VALUES ($1)
       RETURNING tenant_id, display_name, status, created_at, updated_at`,
      [body.display_name],
    );
    return reply.code(201).send(result.rows[0]);
  });

  // GET /tenants — observer + non-white roles see only their own tenant.
  // White cell sees only its own tenant in v1 (no cross-tenant directory yet).
  app.get("/tenants", { preHandler: [requireAuth] }, async (req) => {
    const result = await db.query(
      `SELECT tenant_id, display_name, status, created_at, updated_at
       FROM tenants
       WHERE tenant_id = $1 AND status != 'archived'`,
      [req.claims.tenant_id],
    );
    return { tenants: result.rows };
  });

  // GET /tenants/:id — must match JWT tenant_id.
  app.get<{ Params: { id: string } }>(
    "/tenants/:id",
    { preHandler: [requireAuth, requireOwnTenant] },
    async (req, reply) => {
      TenantIdParams.parse(req.params);
      const result = await db.query(
        `SELECT tenant_id, display_name, status, created_at, updated_at
         FROM tenants
         WHERE tenant_id = $1`,
        [req.params.id],
      );
      if (result.rowCount === 0) return reply.code(404).send({ error: "not_found" });
      return result.rows[0];
    },
  );

  // PATCH /tenants/:id — white only, own tenant.
  app.patch<{ Params: { id: string } }>(
    "/tenants/:id",
    { preHandler: [requireAuth, requireCellRole("white"), requireOwnTenant] },
    async (req, reply) => {
      TenantIdParams.parse(req.params);
      const body = UpdateTenantBody.parse(req.body);
      if (body.display_name === undefined) {
        return reply.code(400).send({ error: "bad_request", reason: "no fields to update" });
      }
      const result = await db.query(
        `UPDATE tenants SET display_name = $1
         WHERE tenant_id = $2
         RETURNING tenant_id, display_name, status, created_at, updated_at`,
        [body.display_name, req.params.id],
      );
      if (result.rowCount === 0) return reply.code(404).send({ error: "not_found" });
      return result.rows[0];
    },
  );

  // DELETE /tenants/:id — soft-delete (status=archived). White only.
  app.delete<{ Params: { id: string } }>(
    "/tenants/:id",
    { preHandler: [requireAuth, requireCellRole("white"), requireOwnTenant] },
    async (req, reply) => {
      TenantIdParams.parse(req.params);
      const result = await db.query(
        `UPDATE tenants SET status = 'archived'
         WHERE tenant_id = $1
         RETURNING tenant_id, display_name, status, created_at, updated_at`,
        [req.params.id],
      );
      if (result.rowCount === 0) return reply.code(404).send({ error: "not_found" });
      return result.rows[0];
    },
  );
}
