import type { FastifyReply, FastifyRequest } from "fastify";
import { JwtClaims, type CellRole } from "./types.js";

declare module "fastify" {
  interface FastifyRequest {
    claims: JwtClaims;
  }
}

declare module "@fastify/jwt" {
  interface FastifyJWT {
    payload: JwtClaims;
    user: JwtClaims;
  }
}

export async function requireAuth(req: FastifyRequest, reply: FastifyReply): Promise<void> {
  try {
    await req.jwtVerify();
  } catch {
    return reply.code(401).send({ error: "unauthorized", reason: "missing or invalid bearer token" });
  }
  const parsed = JwtClaims.safeParse(req.user);
  if (!parsed.success) {
    return reply.code(401).send({ error: "unauthorized", reason: "jwt claims do not match expected shape" });
  }
  req.claims = parsed.data;
}

export function requireCellRole(...allowed: CellRole[]) {
  return async (req: FastifyRequest, reply: FastifyReply): Promise<void> => {
    if (!allowed.includes(req.claims.cell_role)) {
      return reply.code(403).send({
        error: "forbidden",
        reason: `cell_role '${req.claims.cell_role}' not in allowed set: [${allowed.join(", ")}]`,
      });
    }
  };
}

export function requireOwnTenant(
  req: FastifyRequest<{ Params: { id: string } }>,
  reply: FastifyReply,
): void {
  if (req.params.id !== req.claims.tenant_id) {
    reply.code(403).send({
      error: "forbidden",
      reason: "cross-tenant access denied: URL tenant id must match JWT tenant_id",
    });
  }
}
