/**
 * Vitest globalSetup: spin up a docker-postgres for the integration tests
 * and apply migrations against it. Tear it down at the end.
 *
 * Set DATABASE_URL or DOCKER_TEST_DB=skip to bypass docker (e.g., when
 * pointing at an external Postgres that's already migrated).
 */

import { execSync, spawnSync } from "node:child_process";
import { migrate } from "../src/db/migrate.ts";

const CONTAINER_NAME = "almighty-cp-test-pg";
const PG_PORT = process.env.PG_TEST_PORT ?? "55434";
const POSTGRES_PASSWORD = "test";
const DATABASE_URL =
  process.env.TEST_DATABASE_URL ??
  `postgres://postgres:${POSTGRES_PASSWORD}@localhost:${PG_PORT}/postgres`;

function sh(cmd: string): string {
  return execSync(cmd, { stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
}

function isContainerRunning(): boolean {
  try {
    const out = sh(`docker ps --filter name=${CONTAINER_NAME} --format "{{.Names}}"`);
    return out === CONTAINER_NAME;
  } catch {
    return false;
  }
}

async function waitForPostgres(maxAttempts = 30): Promise<void> {
  for (let i = 0; i < maxAttempts; i++) {
    const result = spawnSync(
      "docker",
      ["exec", CONTAINER_NAME, "pg_isready", "-U", "postgres"],
      { stdio: "ignore" },
    );
    if (result.status === 0) return;
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("postgres did not become ready in time");
}

export async function setup(): Promise<() => Promise<void>> {
  if (process.env.DOCKER_TEST_DB === "skip") {
    process.env.TEST_DATABASE_URL = DATABASE_URL;
    await migrate(DATABASE_URL);
    return async () => {};
  }

  // Reuse existing container if it's running, otherwise start fresh.
  if (!isContainerRunning()) {
    try {
      sh(`docker rm -f ${CONTAINER_NAME}`);
    } catch {
      // ignore — container didn't exist
    }
    sh(
      `docker run --rm -d --name ${CONTAINER_NAME} ` +
        `-e POSTGRES_PASSWORD=${POSTGRES_PASSWORD} ` +
        `-p ${PG_PORT}:5432 postgres:16`,
    );
  }

  await waitForPostgres();
  process.env.TEST_DATABASE_URL = DATABASE_URL;
  await migrate(DATABASE_URL);

  return async () => {
    if (process.env.DOCKER_TEST_DB === "keep") return;
    try {
      sh(`docker rm -f ${CONTAINER_NAME}`);
    } catch {
      // ignore
    }
  };
}
