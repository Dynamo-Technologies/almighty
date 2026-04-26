import { z } from "zod";

export const CellRole = z.enum(["white", "blue", "red", "observer"]);
export type CellRole = z.infer<typeof CellRole>;

export const Channel = z.enum(["events", "override_pending", "turn_state", "czml_packets"]);
export type Channel = z.infer<typeof Channel>;

export const JwtClaims = z.object({
  tenant_id: z.string().uuid(),
  cell_role: CellRole,
  sub: z.string().optional(),
});
export type JwtClaims = z.infer<typeof JwtClaims>;

// Channel access matrix per spec WS-304. White-only channels carry decisions
// or pending-review state that must not leak to operator-side cells.
export const CHANNEL_ACCESS: Record<Channel, ReadonlySet<CellRole>> = {
  events: new Set(["white", "blue", "red", "observer"]),
  override_pending: new Set(["white"]),
  turn_state: new Set(["white", "blue", "red", "observer"]),
  czml_packets: new Set(["white", "blue", "red", "observer"]),
};

// Inbound client → server messages.
export const ClientMessage = z.discriminatedUnion("action", [
  z.object({ action: z.literal("subscribe"), channel: Channel }),
  z.object({ action: z.literal("unsubscribe"), channel: Channel }),
  z.object({ action: z.literal("ping") }),
]);
export type ClientMessage = z.infer<typeof ClientMessage>;

// Outbound server → client envelope.
export type ServerMessage =
  | { type: "subscribed"; channel: Channel }
  | { type: "unsubscribed"; channel: Channel }
  | { type: "error"; reason: string }
  | { type: "pong" }
  | { type: "message"; channel: Channel; tenant_id: string; payload: unknown };

// HTTP /publish body. tenant_id is asserted against the JWT inside the route.
export const PublishBody = z.object({
  tenant_id: z.string().uuid(),
  channel: Channel,
  payload: z.unknown(),
});
export type PublishBody = z.infer<typeof PublishBody>;
