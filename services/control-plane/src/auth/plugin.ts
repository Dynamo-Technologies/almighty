/**
 * Fastify auth plugin.
 *
 * - `authenticate`: verifies the bearer token and attaches `request.actor`.
 *   Replies 401 on missing/invalid token.
 * - `requireCellRole(role)`: pre-handler that 403s if `request.actor.cellRole`
 *   doesn't match.
 *
 * Routes that need both call them in sequence on the route's preHandler.
 */

import type { FastifyInstance, FastifyReply, FastifyRequest } from "fastify";
import {
  type Actor,
  type CellRole,
  JwtError,
  extractBearerToken,
  verifyJwt,
} from "./jwt.ts";

declare module "fastify" {
  interface FastifyRequest {
    actor?: Actor;
  }
}

export interface AuthPluginOptions {
  jwtSecret: string;
}

export function registerAuth(
  app: FastifyInstance,
  opts: AuthPluginOptions,
): void {
  app.decorate(
    "authenticate",
    async (request: FastifyRequest, reply: FastifyReply) => {
      const token = extractBearerToken(request.headers.authorization);
      if (!token) {
        return reply
          .code(401)
          .send({ error: "unauthorized", reason: "missing bearer token" });
      }
      try {
        request.actor = await verifyJwt(token, opts.jwtSecret);
      } catch (err) {
        if (err instanceof JwtError) {
          return reply.code(401).send({ error: "unauthorized", reason: err.message });
        }
        throw err;
      }
    },
  );

  app.decorate(
    "requireCellRole",
    (role: CellRole) =>
      async (request: FastifyRequest, reply: FastifyReply) => {
        const actor = request.actor;
        if (!actor) {
          return reply
            .code(401)
            .send({ error: "unauthorized", reason: "no actor on request" });
        }
        if (actor.cellRole !== role) {
          return reply.code(403).send({
            error: "forbidden",
            reason: `required cell_role=${role}; got ${actor.cellRole}`,
          });
        }
      },
  );
}

declare module "fastify" {
  interface FastifyInstance {
    authenticate: (
      request: FastifyRequest,
      reply: FastifyReply,
    ) => Promise<unknown>;
    requireCellRole: (
      role: CellRole,
    ) => (
      request: FastifyRequest,
      reply: FastifyReply,
    ) => Promise<unknown>;
  }
}
