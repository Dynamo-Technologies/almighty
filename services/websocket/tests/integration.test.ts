import { afterAll, beforeAll, describe, expect, it } from "vitest";
import WebSocket from "ws";
import type { AddressInfo } from "node:net";
import type { FastifyInstance } from "fastify";
import { buildApp } from "../src/app.js";
import { Hub } from "../src/hub.js";
import type { CellRole, Channel, ServerMessage } from "../src/types.js";

const JWT_SECRET = "test-secret-".padEnd(40, "x");
const TENANT_A = "11111111-1111-4111-8111-111111111111";
const TENANT_B = "22222222-2222-4222-8222-222222222222";

let app: FastifyInstance;
let hub: Hub;
let baseUrl: string;
let wsBase: string;

beforeAll(async () => {
  const built = await buildApp({
    env: {
      JWT_SECRET,
      PORT: 0,
      HOST: "127.0.0.1",
      LOG_LEVEL: "error",
      MAX_BUFFERED_BYTES: 10 * 1024 * 1024,
    },
  });
  app = built.app;
  hub = built.hub;
  await app.listen({ port: 0, host: "127.0.0.1" });
  const addr = app.server.address() as AddressInfo;
  baseUrl = `http://127.0.0.1:${addr.port}`;
  wsBase = `ws://127.0.0.1:${addr.port}/ws`;
});

afterAll(async () => {
  await app.close();
});

const sign = (claims: { tenant_id: string; cell_role: CellRole }): string => app.jwt.sign(claims);

interface OpenedSocket {
  ws: WebSocket;
  next: () => Promise<ServerMessage>;
  close: () => Promise<void>;
}

async function open(token: string | undefined): Promise<OpenedSocket> {
  const url = token ? `${wsBase}?token=${encodeURIComponent(token)}` : wsBase;
  const ws = new WebSocket(url);
  const queue: ServerMessage[] = [];
  const waiters: Array<(m: ServerMessage) => void> = [];

  ws.on("message", (raw: Buffer) => {
    const m = JSON.parse(raw.toString("utf-8")) as ServerMessage;
    const w = waiters.shift();
    if (w) w(m);
    else queue.push(m);
  });

  // The HTTP upgrade succeeds before the server's per-route auth runs, so
  // an unauthorized connection sees `open` followed immediately by `close`
  // with code 1008. Treat any close within 150 ms of open as a rejection.
  await new Promise<void>((resolve, reject) => {
    let opened = false;
    let settled = false;
    const settle = (fn: () => void) => {
      if (settled) return;
      settled = true;
      fn();
    };
    ws.once("error", (err) => settle(() => reject(err)));
    ws.once("close", (code, reasonBuf) => {
      const reason = reasonBuf?.toString() || "";
      if (opened) {
        settle(() => reject(new Error(`closed shortly after open: ${code} ${reason}`)));
      } else {
        settle(() => reject(new Error(`closed before open: ${code} ${reason}`)));
      }
    });
    ws.once("open", () => {
      opened = true;
      setTimeout(() => settle(resolve), 150);
    });
  });

  return {
    ws,
    next: () =>
      new Promise<ServerMessage>((resolve) => {
        const m = queue.shift();
        if (m) resolve(m);
        else waiters.push(resolve);
      }),
    close: () =>
      new Promise<void>((resolve) => {
        if (ws.readyState === WebSocket.CLOSED) return resolve();
        ws.once("close", () => resolve());
        ws.close();
      }),
  };
}

async function subscribeOk(s: OpenedSocket, channel: Channel): Promise<void> {
  s.ws.send(JSON.stringify({ action: "subscribe", channel }));
  const ack = await s.next();
  if (ack.type !== "subscribed" || ack.channel !== channel) {
    throw new Error(`expected subscribed, got ${JSON.stringify(ack)}`);
  }
}

async function publish(token: string, body: { tenant_id: string; channel: Channel; payload: unknown }): Promise<Response> {
  return fetch(`${baseUrl}/publish`, {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
}

describe("auth", () => {
  it("rejects WS connection without a token", async () => {
    await expect(open(undefined)).rejects.toBeDefined();
  });

  it("rejects WS connection with invalid token", async () => {
    await expect(open("not-a-jwt")).rejects.toBeDefined();
  });

  it("accepts WS connection with valid token", async () => {
    const s = await open(sign({ tenant_id: TENANT_A, cell_role: "white" }));
    expect(s.ws.readyState).toBe(WebSocket.OPEN);
    await s.close();
  });
});

describe("channel role gating", () => {
  it.each([
    ["white", "events", true],
    ["white", "override_pending", true],
    ["white", "turn_state", true],
    ["white", "czml_packets", true],
    ["blue", "events", true],
    ["blue", "override_pending", false],
    ["blue", "turn_state", true],
    ["blue", "czml_packets", true],
    ["red", "override_pending", false],
    ["observer", "override_pending", false],
    ["observer", "events", true],
  ] as const)("%s on %s → allowed=%s", async (role, channel, allowed) => {
    const s = await open(sign({ tenant_id: TENANT_A, cell_role: role }));
    s.ws.send(JSON.stringify({ action: "subscribe", channel }));
    const reply = await s.next();
    if (allowed) {
      expect(reply).toMatchObject({ type: "subscribed", channel });
    } else {
      expect(reply).toMatchObject({ type: "error" });
    }
    await s.close();
  });
});

describe("HTTP /publish", () => {
  it("rejects unauthenticated publish", async () => {
    const res = await fetch(`${baseUrl}/publish`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ tenant_id: TENANT_A, channel: "events", payload: { a: 1 } }),
    });
    expect(res.status).toBe(401);
  });

  it("rejects non-white roles", async () => {
    const res = await publish(sign({ tenant_id: TENANT_A, cell_role: "blue" }), {
      tenant_id: TENANT_A,
      channel: "events",
      payload: { a: 1 },
    });
    expect(res.status).toBe(403);
  });

  it("rejects cross-tenant publish (body tenant ≠ JWT tenant)", async () => {
    const res = await publish(sign({ tenant_id: TENANT_A, cell_role: "white" }), {
      tenant_id: TENANT_B,
      channel: "events",
      payload: { a: 1 },
    });
    expect(res.status).toBe(403);
  });

  it("delivers to a subscribed white-cell connection in the same tenant", async () => {
    const s = await open(sign({ tenant_id: TENANT_A, cell_role: "white" }));
    await subscribeOk(s, "events");

    const res = await publish(sign({ tenant_id: TENANT_A, cell_role: "white" }), {
      tenant_id: TENANT_A,
      channel: "events",
      payload: { hello: "world" },
    });
    expect(res.status).toBe(202);
    const result = (await res.json()) as { delivered: number; dropped: number };
    expect(result.delivered).toBe(1);

    const m = await s.next();
    expect(m).toMatchObject({ type: "message", channel: "events", tenant_id: TENANT_A, payload: { hello: "world" } });
    await s.close();
  });

  it("does not deliver to connections that did not subscribe", async () => {
    const subbed = await open(sign({ tenant_id: TENANT_A, cell_role: "white" }));
    const unsubbed = await open(sign({ tenant_id: TENANT_A, cell_role: "white" }));
    await subscribeOk(subbed, "turn_state");

    await publish(sign({ tenant_id: TENANT_A, cell_role: "white" }), {
      tenant_id: TENANT_A,
      channel: "turn_state",
      payload: { turn: 5 },
    });

    const m = await subbed.next();
    expect(m).toMatchObject({ type: "message", channel: "turn_state" });

    // Unsubbed connection should have nothing in queue. Use a short race.
    const got = await Promise.race([
      unsubbed.next(),
      new Promise<"timeout">((r) => setTimeout(() => r("timeout"), 250)),
    ]);
    expect(got).toBe("timeout");
    await subbed.close();
    await unsubbed.close();
  });
});

describe("cross-tenant isolation under load (4 tenants × 8 connections)", () => {
  it("publishes to tenant A reach only tenant A's subscribers", async () => {
    const tenants = [
      "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
      "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    ];
    const conns: Record<string, OpenedSocket[]> = {};
    for (const t of tenants) {
      conns[t] = [];
      for (let i = 0; i < 8; i++) {
        const s = await open(sign({ tenant_id: t, cell_role: "white" }));
        await subscribeOk(s, "events");
        conns[t].push(s);
      }
    }
    expect(hub.connectionCountForTenant(tenants[0])).toBe(8);

    // Publish 25 messages to each tenant in interleaved order. Total 100.
    const counts: Record<string, number> = Object.fromEntries(tenants.map((t) => [t, 0]));
    for (const t of tenants) {
      for (const s of conns[t]) {
        s.ws.on("message", (raw: Buffer) => {
          const m = JSON.parse(raw.toString("utf-8")) as ServerMessage;
          if (m.type === "message") counts[m.tenant_id]++;
        });
      }
    }

    for (let i = 0; i < 25; i++) {
      for (const t of tenants) {
        await publish(sign({ tenant_id: t, cell_role: "white" }), {
          tenant_id: t,
          channel: "events",
          payload: { i },
        });
      }
    }

    // Give the event loop a few ticks to drain.
    await new Promise((r) => setTimeout(r, 200));

    // Each tenant: 25 publishes × 8 connections = 200 messages received. The
    // listeners attached above receive in addition to the per-socket queue,
    // so the assertion is "exactly 200 per tenant, no leak across tenants."
    for (const t of tenants) {
      expect(counts[t]).toBe(200);
    }

    for (const t of tenants) for (const s of conns[t]) await s.close();
  });
});
