/**
 * Almighty control plane — Fastify entrypoint.
 *
 * Today this exposes only the WS-302 turn-advance endpoint. WS-301 will
 * add the tenant + scenario CRUD surface against the same app instance.
 */

import Fastify, { type FastifyInstance } from "fastify";
import { registerAuth } from "./auth/plugin.ts";
import { loadConfig } from "./config.ts";
import { closePool, getPool } from "./db/pool.ts";
import { registerTurnRoutes } from "./turn-controller/routes.ts";

export interface BuildAppOptions {
  jwtSecret: string;
  databaseUrl: string;
  logLevel?: string;
}

export function buildApp(opts: BuildAppOptions): FastifyInstance {
  const app = Fastify({
    logger: {
      level: opts.logLevel ?? "info",
      // Don't pretty-print in tests — keeps output stable.
      transport: process.env.NODE_ENV === "test"
        ? undefined
        : { target: "pino/file", options: { destination: 1 } },
    },
  });

  const pool = getPool(opts.databaseUrl);
  registerAuth(app, { jwtSecret: opts.jwtSecret });
  registerTurnRoutes(app, pool);

  app.get("/healthz", async () => ({ ok: true }));

  return app;
}

async function main(): Promise<void> {
  const config = loadConfig();
  const app = buildApp({
    jwtSecret: config.jwtSecret,
    databaseUrl: config.databaseUrl,
    logLevel: config.logLevel,
  });

  const shutdown = async () => {
    app.log.info("shutdown initiated");
    await app.close();
    await closePool();
    process.exit(0);
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);

  try {
    await app.listen({ port: config.port, host: "0.0.0.0" });
  } catch (err) {
    app.log.error(err);
    process.exit(1);
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  void main();
}
