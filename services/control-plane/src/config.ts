/**
 * Environment-driven configuration for the control plane.
 *
 * Required vars:
 *   DATABASE_URL  Postgres connection string
 *   JWT_SECRET    HS256 signing secret
 *
 * Optional vars:
 *   PORT          default 8080
 *   LOG_LEVEL     default info
 */

export interface Config {
  port: number;
  databaseUrl: string;
  jwtSecret: string;
  logLevel: string;
}

function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required env var ${name}`);
  }
  return value;
}

export function loadConfig(): Config {
  return {
    port: Number(process.env.PORT ?? 8080),
    databaseUrl: required("DATABASE_URL"),
    jwtSecret: required("JWT_SECRET"),
    logLevel: process.env.LOG_LEVEL ?? "info",
  };
}
