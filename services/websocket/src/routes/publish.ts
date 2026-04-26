import type { FastifyInstance } from "fastify";
import { requireAuth, requireCellRole } from "../auth.js";
import { PublishBody } from "../types.js";
import type { Hub } from "../hub.js";

export async function registerPublishRoute(app: FastifyInstance, hub: Hub): Promise<void> {
  // Internal ingress: the kernel and control-plane sign a white-cell JWT for
  // their own tenant_id and POST messages here. Cross-tenant publish is
  // denied by checking JWT.tenant_id against the body's tenant_id.
  app.post(
    "/publish",
    { preHandler: [requireAuth, requireCellRole("white")] },
    async (req, reply) => {
      const body = PublishBody.parse(req.body);
      if (body.tenant_id !== req.claims.tenant_id) {
        return reply.code(403).send({
          error: "forbidden",
          reason: "cross-tenant publish denied: body tenant_id must match JWT tenant_id",
        });
      }
      const result = hub.publish(body.tenant_id, body.channel, body.payload);
      return reply.code(202).send(result);
    },
  );
}
