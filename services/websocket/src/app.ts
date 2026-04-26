import Fastify, { type FastifyInstance } from "fastify";
import fastifyJwt from "@fastify/jwt";
import fastifyWebsocket from "@fastify/websocket";
import { ZodError } from "zod";
import type { Env } from "./config.js";
import { Hub } from "./hub.js";
import { registerWsRoute } from "./routes/ws.js";
import { registerPublishRoute } from "./routes/publish.js";

export interface BuildAppOptions {
  env: Env;
  hub?: Hub;
}

export async function buildApp({ env, hub }: BuildAppOptions): Promise<{
  app: FastifyInstance;
  hub: Hub;
}> {
  const app = Fastify({ logger: { level: env.LOG_LEVEL } });
  const internalHub = hub ?? new Hub(env.MAX_BUFFERED_BYTES);

  await app.register(fastifyJwt, { secret: env.JWT_SECRET });
  await app.register(fastifyWebsocket);

  app.setErrorHandler((err, _req, reply) => {
    if (err instanceof ZodError) {
      return reply.code(400).send({ error: "bad_request", issues: err.issues });
    }
    app.log.error(err);
    return reply.code(500).send({ error: "internal_error" });
  });

  app.get("/healthz", async () => ({ ok: true, ...internalHub.getMetrics() }));

  await registerWsRoute(app, internalHub);
  await registerPublishRoute(app, internalHub);

  return { app, hub: internalHub };
}
