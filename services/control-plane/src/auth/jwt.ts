/**
 * JWT verification.
 *
 * v1: HS256 with a shared secret loaded from JWT_SECRET. Production
 * deployment will switch to RS256 + key rotation; that's out of scope for
 * WS-302. The actor shape is whatever the issuer puts on the JWT — the
 * control plane only enforces the claims it cares about.
 */

import { jwtVerify } from "jose";

export type CellRole = "white" | "blue" | "red" | "observer";

export interface Actor {
  /** Subject — usually email or user UUID. */
  sub: string;
  /** Tenant the actor belongs to. */
  tenantId: string;
  /** Role within the tenant. */
  cellRole: CellRole;
}

const VALID_ROLES: ReadonlySet<string> = new Set([
  "white",
  "blue",
  "red",
  "observer",
]);

export class JwtError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "JwtError";
  }
}

export async function verifyJwt(token: string, secret: string): Promise<Actor> {
  const key = new TextEncoder().encode(secret);
  let payload: Record<string, unknown>;
  try {
    const result = await jwtVerify(token, key);
    payload = result.payload as Record<string, unknown>;
  } catch (err) {
    throw new JwtError(`invalid token: ${(err as Error).message}`);
  }

  const sub = payload["sub"];
  const tenantId = payload["tenant_id"];
  const cellRole = payload["cell_role"];

  if (typeof sub !== "string" || sub.length === 0) {
    throw new JwtError("missing claim: sub");
  }
  if (typeof tenantId !== "string" || tenantId.length === 0) {
    throw new JwtError("missing claim: tenant_id");
  }
  if (typeof cellRole !== "string" || !VALID_ROLES.has(cellRole)) {
    throw new JwtError(
      `invalid claim cell_role: expected one of ${[...VALID_ROLES].join(", ")}`,
    );
  }

  return { sub, tenantId, cellRole: cellRole as CellRole };
}

export function extractBearerToken(
  authorizationHeader: string | undefined,
): string | null {
  if (!authorizationHeader) return null;
  const parts = authorizationHeader.split(" ");
  if (parts.length !== 2 || parts[0]?.toLowerCase() !== "bearer") return null;
  return parts[1] ?? null;
}
