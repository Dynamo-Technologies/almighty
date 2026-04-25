import type { FastifyInstance } from "fastify";
import type { Pool } from "../db.js";
import { requireAuth, requireCellRole, requireOwnTenant } from "../auth.js";
import {
  CreateScenarioBody,
  ScenarioIdParams,
  TenantIdParams,
  UpdateScenarioBody,
} from "../types.js";

export async function registerScenarioRoutes(app: FastifyInstance, db: Pool): Promise<void> {
  // POST /tenants/:id/scenarios — white only.
  app.post<{ Params: { id: string } }>(
    "/tenants/:id/scenarios",
    { preHandler: [requireAuth, requireCellRole("white"), requireOwnTenant] },
    async (req, reply) => {
      TenantIdParams.parse(req.params);
      const body = CreateScenarioBody.parse(req.body);
      const result = await db.query(
        `INSERT INTO scenarios (tenant_id, display_name, description)
         VALUES ($1, $2, $3)
         RETURNING scenario_id, tenant_id, display_name, status, description, created_at, updated_at`,
        [req.params.id, body.display_name, body.description],
      );
      return reply.code(201).send(result.rows[0]);
    },
  );

  // GET /tenants/:id/scenarios — all roles within own tenant.
  app.get<{ Params: { id: string } }>(
    "/tenants/:id/scenarios",
    { preHandler: [requireAuth, requireOwnTenant] },
    async (req) => {
      TenantIdParams.parse(req.params);
      const result = await db.query(
        `SELECT scenario_id, tenant_id, display_name, status, description, created_at, updated_at
         FROM scenarios
         WHERE tenant_id = $1 AND status != 'archived'
         ORDER BY created_at DESC`,
        [req.params.id],
      );
      return { scenarios: result.rows };
    },
  );

  // GET /tenants/:id/scenarios/:sid — all roles within own tenant.
  app.get<{ Params: { id: string; sid: string } }>(
    "/tenants/:id/scenarios/:sid",
    { preHandler: [requireAuth, requireOwnTenant] },
    async (req, reply) => {
      ScenarioIdParams.parse(req.params);
      const result = await db.query(
        `SELECT scenario_id, tenant_id, display_name, status, description, created_at, updated_at
         FROM scenarios
         WHERE tenant_id = $1 AND scenario_id = $2`,
        [req.params.id, req.params.sid],
      );
      if (result.rowCount === 0) return reply.code(404).send({ error: "not_found" });
      return result.rows[0];
    },
  );

  // PATCH /tenants/:id/scenarios/:sid — white only.
  app.patch<{ Params: { id: string; sid: string } }>(
    "/tenants/:id/scenarios/:sid",
    { preHandler: [requireAuth, requireCellRole("white"), requireOwnTenant] },
    async (req, reply) => {
      ScenarioIdParams.parse(req.params);
      const body = UpdateScenarioBody.parse(req.body);
      const sets: string[] = [];
      const vals: unknown[] = [];
      if (body.display_name !== undefined) {
        vals.push(body.display_name);
        sets.push(`display_name = $${vals.length}`);
      }
      if (body.description !== undefined) {
        vals.push(body.description);
        sets.push(`description = $${vals.length}`);
      }
      if (body.status !== undefined) {
        vals.push(body.status);
        sets.push(`status = $${vals.length}`);
      }
      if (sets.length === 0) {
        return reply.code(400).send({ error: "bad_request", reason: "no fields to update" });
      }
      vals.push(req.params.id, req.params.sid);
      const result = await db.query(
        `UPDATE scenarios SET ${sets.join(", ")}
         WHERE tenant_id = $${vals.length - 1} AND scenario_id = $${vals.length}
         RETURNING scenario_id, tenant_id, display_name, status, description, created_at, updated_at`,
        vals,
      );
      if (result.rowCount === 0) return reply.code(404).send({ error: "not_found" });
      return result.rows[0];
    },
  );

  // DELETE /tenants/:id/scenarios/:sid — soft-delete. White only.
  app.delete<{ Params: { id: string; sid: string } }>(
    "/tenants/:id/scenarios/:sid",
    { preHandler: [requireAuth, requireCellRole("white"), requireOwnTenant] },
    async (req, reply) => {
      ScenarioIdParams.parse(req.params);
      const result = await db.query(
        `UPDATE scenarios SET status = 'archived'
         WHERE tenant_id = $1 AND scenario_id = $2
         RETURNING scenario_id, tenant_id, display_name, status, description, created_at, updated_at`,
        [req.params.id, req.params.sid],
      );
      if (result.rowCount === 0) return reply.code(404).send({ error: "not_found" });
      return result.rows[0];
    },
  );
}
