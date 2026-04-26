import { loadEnv } from "./config.js";
import { buildApp } from "./app.js";

const env = loadEnv();
const { app } = await buildApp({ env });

try {
  await app.listen({ port: env.PORT, host: env.HOST });
  app.log.info(`websocket listening on ${env.HOST}:${env.PORT}`);
} catch (err) {
  app.log.error(err);
  process.exit(1);
}
