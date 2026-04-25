import type { FastifyInstance } from "fastify";
import type pg from "pg";
import {
  ScenarioNotFoundError,
  TurnAdvanceConflictError,
  advanceTurn,
} from "./service.ts";

interface AdvanceTurnParams {
  id: string;   // tenant_id
  sid: string;  // scenario_id
}

export function registerTurnRoutes(
  app: FastifyInstance,
  pool: pg.Pool,
): void {
  app.post<{ Params: AdvanceTurnParams }>(
    "/tenants/:id/scenarios/:sid/turns/advance",
    {
      preHandler: [app.authenticate, app.requireCellRole("white")],
    },
    async (request, reply) => {
      const { id: tenantId, sid: scenarioId } = request.params;
      const actor = request.actor!; // authenticate guarantees this

      // Cross-tenant isolation: the JWT's tenant_id must match the URL's.
      if (actor.tenantId !== tenantId) {
        return reply.code(403).send({
          error: "forbidden",
          reason: "tenant_id in token does not match URL",
        });
      }

      try {
        const result = await advanceTurn(pool, { tenantId, scenarioId });
        return reply.code(200).send(result);
      } catch (err) {
        if (err instanceof TurnAdvanceConflictError) {
          return reply.code(409).send({
            error: "conflict",
            reason: err.message,
          });
        }
        if (err instanceof ScenarioNotFoundError) {
          return reply.code(404).send({
            error: "not_found",
            reason: err.message,
          });
        }
        throw err;
      }
    },
  );
}
