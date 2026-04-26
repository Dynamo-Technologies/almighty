import type { WebSocket } from "ws";
import type { Channel, JwtClaims, ServerMessage } from "./types.js";
import { CHANNEL_ACCESS } from "./types.js";

export interface Connection {
  id: string;
  socket: WebSocket;
  claims: JwtClaims;
  subscriptions: Set<Channel>;
}

export interface HubMetrics {
  connections: number;
  drops: number;
  publishes: number;
  rejected: number;
}

export interface PublishResult {
  delivered: number;
  dropped: number;
}

/**
 * In-process pub/sub hub. v1 hackathon scope; horizontal scaling beyond a
 * single instance lands behind a Redis adapter swap (documented in README).
 *
 * Two cross-cutting invariants the hub enforces:
 *   1. Cross-tenant isolation. publish(tenant, ...) only ever reaches
 *      connections whose JWT-derived tenant_id matches `tenant`.
 *   2. Channel role gating. subscribe(conn, channel) checks
 *      CHANNEL_ACCESS[channel] against conn.claims.cell_role.
 */
export class Hub {
  private readonly connectionsByTenant = new Map<string, Set<Connection>>();
  private readonly metrics: HubMetrics = { connections: 0, drops: 0, publishes: 0, rejected: 0 };

  constructor(private readonly maxBufferedBytes: number) {}

  register(conn: Connection): void {
    const bucket = this.connectionsByTenant.get(conn.claims.tenant_id) ?? new Set();
    bucket.add(conn);
    this.connectionsByTenant.set(conn.claims.tenant_id, bucket);
    this.metrics.connections++;
  }

  unregister(conn: Connection): void {
    const bucket = this.connectionsByTenant.get(conn.claims.tenant_id);
    if (!bucket) return;
    bucket.delete(conn);
    if (bucket.size === 0) this.connectionsByTenant.delete(conn.claims.tenant_id);
    this.metrics.connections--;
  }

  /**
   * Returns true on subscribe, false if the role is not permitted on the channel.
   */
  subscribe(conn: Connection, channel: Channel): boolean {
    if (!CHANNEL_ACCESS[channel].has(conn.claims.cell_role)) {
      this.metrics.rejected++;
      return false;
    }
    conn.subscriptions.add(channel);
    return true;
  }

  unsubscribe(conn: Connection, channel: Channel): void {
    conn.subscriptions.delete(channel);
  }

  publish(tenantId: string, channel: Channel, payload: unknown): PublishResult {
    this.metrics.publishes++;
    const result: PublishResult = { delivered: 0, dropped: 0 };
    const bucket = this.connectionsByTenant.get(tenantId);
    if (!bucket) return result;

    const envelope: ServerMessage = { type: "message", channel, tenant_id: tenantId, payload };
    const json = JSON.stringify(envelope);

    for (const conn of bucket) {
      if (!conn.subscriptions.has(channel)) continue;
      if (conn.socket.bufferedAmount > this.maxBufferedBytes) {
        this.metrics.drops++;
        result.dropped++;
        continue;
      }
      conn.socket.send(json);
      result.delivered++;
    }
    return result;
  }

  getMetrics(): Readonly<HubMetrics> {
    return { ...this.metrics };
  }

  /**
   * Test helper. Returns the number of live connections for a tenant.
   */
  connectionCountForTenant(tenantId: string): number {
    return this.connectionsByTenant.get(tenantId)?.size ?? 0;
  }
}
