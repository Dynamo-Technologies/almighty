import type { FastifyInstance } from "fastify";
import type { Pool } from "../db.js";
import { requireAuth, requireOwnTenant } from "../auth.js";
import { ScenarioIdParams } from "../types.js";

// Read-only access to the committed event log for a scenario. Powers WS-506
// AAR replay; populated by the kernel (WS-104 namespacing) once agents
// (WS-401–405) commit events through the DAG.
//
// All cell roles within the tenant can read (review-only surface; mutations
// happen via agent runtime, not here).
export async function registerEventRoutes(app: FastifyInstance, db: Pool): Promise<void> {
  app.get<{
    Params: { id: string; sid: string };
    Querystring: { since_ts?: string; until_ts?: string; limit?: string };
  }>(
    "/tenants/:id/scenarios/:sid/events",
    { preHandler: [requireAuth, requireOwnTenant] },
    async (req, reply) => {
      ScenarioIdParams.parse(req.params);

      const limitRaw = req.query.limit;
      const limit = Math.min(
        Number.isFinite(Number(limitRaw)) ? Number(limitRaw) : 5000,
        10_000,
      );
      const sinceTs = req.query.since_ts ?? null;
      const untilTs = req.query.until_ts ?? null;

      const params: unknown[] = [req.params.id, req.params.sid];
      const conds: string[] = ["tenant_id = $1", "scenario_id = $2"];
      if (sinceTs) {
        params.push(sinceTs);
        conds.push(`ts >= $${params.length}`);
      }
      if (untilTs) {
        params.push(untilTs);
        conds.push(`ts <= $${params.length}`);
      }
      params.push(limit);

      const result = await db.query(
        `SELECT event_id, tenant_id, scenario_id, turn,
                source_officer_type, source_entity_id, action_verb,
                payload, causal_predecessors, ts, created_at
         FROM events
         WHERE ${conds.join(" AND ")}
         ORDER BY ts ASC, event_id ASC
         LIMIT $${params.length}`,
        params,
      );
      return reply.send({ events: result.rows, count: result.rowCount });
    },
  );
}
