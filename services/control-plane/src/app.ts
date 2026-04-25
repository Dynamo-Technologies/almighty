import Fastify, { type FastifyInstance } from "fastify";
import fastifyJwt from "@fastify/jwt";
import { ZodError } from "zod";
import type { Env } from "./config.js";
import { createPool, type Pool } from "./db.js";
import { registerTenantRoutes } from "./routes/tenants.js";
import { registerScenarioRoutes } from "./routes/scenarios.js";

export interface BuildAppOptions {
  env: Env;
  pool?: Pool;
}

export async function buildApp({ env, pool }: BuildAppOptions): Promise<{
  app: FastifyInstance;
  pool: Pool;
}> {
  const app = Fastify({ logger: { level: env.LOG_LEVEL } });
  const db = pool ?? createPool(env.DATABASE_URL);

  await app.register(fastifyJwt, { secret: env.JWT_SECRET });

  app.setErrorHandler((err, _req, reply) => {
    if (err instanceof ZodError) {
      return reply.code(400).send({ error: "bad_request", issues: err.issues });
    }
    app.log.error(err);
    return reply.code(500).send({ error: "internal_error" });
  });

  app.get("/healthz", async () => ({ ok: true }));

  await registerTenantRoutes(app, db);
  await registerScenarioRoutes(app, db);

  app.addHook("onClose", async () => {
    if (!pool) await db.end();
  });

  return { app, pool: db };
}
