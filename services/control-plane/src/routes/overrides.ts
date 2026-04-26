import type { FastifyInstance } from "fastify";
import type { Pool } from "../db.js";
import { requireAuth, requireCellRole, requireOwnTenant } from "../auth.js";
import {
  CreateOverridePolicyBody,
  EventIdParams,
  ManualDecisionBody,
  OverrideIdParams,
  ScenarioIdParams,
} from "../types.js";
import {
  EventNotFoundError,
  PolicyNotFoundError,
  createPolicy,
  listPolicies,
  manualDecision,
  revokePolicy,
} from "../override-gateway.js";

export async function registerOverrideRoutes(app: FastifyInstance, db: Pool): Promise<void> {
  // POST /tenants/:id/scenarios/:sid/overrides — author policy. White only.
  app.post<{ Params: { id: string; sid: string } }>(
    "/tenants/:id/scenarios/:sid/overrides",
    { preHandler: [requireAuth, requireCellRole("white"), requireOwnTenant] },
    async (req, reply) => {
      ScenarioIdParams.parse(req.params);
      const body = CreateOverridePolicyBody.parse(req.body);

      // `created_by` must be a UUID; we use the JWT `sub` claim. If the
      // claim isn't a UUID we fall back to a deterministic per-tenant
      // sentinel so the column constraint is satisfied. v1 only — once
      // a real user-management story lands, this can require a sub.
      const createdBy = isUuid(req.claims.sub) ? req.claims.sub! : req.claims.tenant_id;

      try {
        const policy = await createPolicy(db, {
          tenantId: req.params.id,
          scenarioId: req.params.sid,
          scope: body.scope,
          action: body.action,
          ttlTurns: body.ttl_turns,
          rationale: body.rationale,
          createdBy,
          eventId: body.event_id,
          agentEntityId: body.agent_entity_id,
          targetTurn: body.target_turn,
        });
        return reply.code(201).send(policy);
      } catch (err) {
        if (err instanceof EventNotFoundError) {
          return reply.code(404).send({ error: "not_found", reason: err.message });
        }
        throw err;
      }
    },
  );

  // GET /tenants/:id/scenarios/:sid/overrides — list active policies.
  // All roles within own tenant.
  app.get<{ Params: { id: string; sid: string } }>(
    "/tenants/:id/scenarios/:sid/overrides",
    { preHandler: [requireAuth, requireOwnTenant] },
    async (req) => {
      ScenarioIdParams.parse(req.params);
      const policies = await listPolicies(db, {
        tenantId: req.params.id,
        scenarioId: req.params.sid,
      });
      return { policies };
    },
  );

  // DELETE /tenants/:id/scenarios/:sid/overrides/:oid — revoke. White only.
  app.delete<{ Params: { id: string; sid: string; oid: string } }>(
    "/tenants/:id/scenarios/:sid/overrides/:oid",
    { preHandler: [requireAuth, requireCellRole("white"), requireOwnTenant] },
    async (req, reply) => {
      OverrideIdParams.parse(req.params);
      const revokedBy = isUuid(req.claims.sub) ? req.claims.sub! : req.claims.tenant_id;
      try {
        const policy = await revokePolicy(db, {
          tenantId: req.params.id,
          scenarioId: req.params.sid,
          policyId: req.params.oid,
          revokedBy,
        });
        return reply.code(200).send(policy);
      } catch (err) {
        if (err instanceof PolicyNotFoundError) {
          return reply.code(404).send({ error: "not_found", reason: err.message });
        }
        throw err;
      }
    },
  );

  // POST /tenants/:id/scenarios/:sid/events/:eid/decision — manual review
  // decision. Persists an override_decision row that resolves a held event.
  // White only.
  app.post<{ Params: { id: string; sid: string; eid: string } }>(
    "/tenants/:id/scenarios/:sid/events/:eid/decision",
    { preHandler: [requireAuth, requireCellRole("white"), requireOwnTenant] },
    async (req, reply) => {
      EventIdParams.parse(req.params);
      const body = ManualDecisionBody.parse(req.body);
      const decidedBy = isUuid(req.claims.sub) ? req.claims.sub! : req.claims.tenant_id;
      try {
        const result = await manualDecision(db, {
          tenantId: req.params.id,
          scenarioId: req.params.sid,
          eventId: req.params.eid,
          outcome: body.outcome,
          decidedBy,
          rationale: body.rationale,
        });
        return reply.code(201).send(result);
      } catch (err) {
        if (err instanceof EventNotFoundError) {
          return reply.code(404).send({ error: "not_found", reason: err.message });
        }
        throw err;
      }
    },
  );
}

function isUuid(s: string | undefined): s is string {
  if (!s) return false;
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s);
}
