import type { FastifyInstance } from "fastify";
import type { WebSocket } from "ws";
import { randomUUID } from "node:crypto";
import { ClientMessage, JwtClaims, type ServerMessage } from "../types.js";
import type { Hub, Connection } from "../hub.js";

function send(socket: WebSocket, msg: ServerMessage): void {
  socket.send(JSON.stringify(msg));
}

export async function registerWsRoute(app: FastifyInstance, hub: Hub): Promise<void> {
  app.get("/ws", { websocket: true }, (socket, req) => {
    // Token may arrive via Sec-WebSocket-Protocol subprotocol or `?token=` query.
    // The browser WebSocket API surfaces the first as the second arg of `new
    // WebSocket(url, protocols)`; CLI clients tend to use the query param.
    const protocolHeader = req.headers["sec-websocket-protocol"];
    const protocolToken = Array.isArray(protocolHeader)
      ? protocolHeader[0]
      : protocolHeader?.split(",").map((s) => s.trim()).find((s) => s.length > 0);
    const queryToken = (req.query as { token?: string } | undefined)?.token;
    const token = protocolToken ?? queryToken;

    if (!token) {
      send(socket, { type: "error", reason: "missing token" });
      socket.close(1008, "unauthorized");
      return;
    }

    let claims: JwtClaims;
    try {
      const decoded = app.jwt.verify(token);
      const parsed = JwtClaims.safeParse(decoded);
      if (!parsed.success) throw new Error("jwt claims malformed");
      claims = parsed.data;
    } catch {
      send(socket, { type: "error", reason: "invalid token" });
      socket.close(1008, "unauthorized");
      return;
    }

    const conn: Connection = {
      id: randomUUID(),
      socket,
      claims,
      subscriptions: new Set(),
    };
    hub.register(conn);
    app.log.info({ tenant_id: claims.tenant_id, conn_id: conn.id }, "ws connected");

    socket.on("message", (raw: Buffer) => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(raw.toString("utf-8"));
      } catch {
        send(socket, { type: "error", reason: "invalid json" });
        return;
      }
      const msg = ClientMessage.safeParse(parsed);
      if (!msg.success) {
        send(socket, { type: "error", reason: "invalid message" });
        return;
      }
      switch (msg.data.action) {
        case "subscribe": {
          const ok = hub.subscribe(conn, msg.data.channel);
          if (!ok) {
            send(socket, { type: "error", reason: `cell_role '${claims.cell_role}' cannot subscribe to '${msg.data.channel}'` });
            return;
          }
          send(socket, { type: "subscribed", channel: msg.data.channel });
          return;
        }
        case "unsubscribe": {
          hub.unsubscribe(conn, msg.data.channel);
          send(socket, { type: "unsubscribed", channel: msg.data.channel });
          return;
        }
        case "ping": {
          send(socket, { type: "pong" });
          return;
        }
      }
    });

    socket.on("close", () => {
      hub.unregister(conn);
      app.log.info({ tenant_id: claims.tenant_id, conn_id: conn.id }, "ws disconnected");
    });
  });
}
