import type { FastifyInstance } from "fastify";
import type { Pool } from "../db.js";
import { requireAuth, requireCellRole, requireOwnTenant } from "../auth.js";
import { ScenarioIdParams } from "../types.js";
import {
  ScenarioNotFoundError,
  TurnAdvanceConflictError,
  advanceTurn,
} from "../turn-controller.js";

export async function registerTurnRoutes(
  app: FastifyInstance,
  db: Pool,
): Promise<void> {
  // POST /tenants/:id/scenarios/:sid/turns/advance — white cell only.
  // Owned by WS-302 (#18).
  app.post<{ Params: { id: string; sid: string } }>(
    "/tenants/:id/scenarios/:sid/turns/advance",
    {
      preHandler: [requireAuth, requireCellRole("white"), requireOwnTenant],
    },
    async (req, reply) => {
      ScenarioIdParams.parse(req.params);
      try {
        const result = await advanceTurn(db, {
          tenantId: req.params.id,
          scenarioId: req.params.sid,
        });
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
