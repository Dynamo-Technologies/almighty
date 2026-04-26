import Fastify, { type FastifyInstance } from "fastify";
import fastifyJwt from "@fastify/jwt";
import fastifyCors from "@fastify/cors";
import { ZodError } from "zod";
import type { Env } from "./config.js";
import { createPool, type Pool } from "./db.js";
import { registerTenantRoutes } from "./routes/tenants.js";
import { registerScenarioRoutes } from "./routes/scenarios.js";
import { registerTurnRoutes } from "./routes/turns.js";
import { registerOverrideRoutes } from "./routes/overrides.js";
import { registerEventRoutes } from "./routes/events.js";

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

  // Permissive CORS for dev — the renderer (Vite on :5173) is on a different
  // origin than the control-plane (:4000). v1 reflects the request origin and
  // allows the Authorization header. Production should pin to a known origin
  // list via env.
  await app.register(fastifyCors, {
    origin: true,
    credentials: true,
    allowedHeaders: ["content-type", "authorization"],
    methods: ["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
  });

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
  await registerTurnRoutes(app, db);
  await registerOverrideRoutes(app, db);
  await registerEventRoutes(app, db);

  app.addHook("onClose", async () => {
    if (!pool) await db.end();
  });

  return { app, pool: db };
}
