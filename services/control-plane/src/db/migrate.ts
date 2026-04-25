/**
 * Minimal migration runner.
 *
 * Walks ./migrations/*.sql in lexicographic order and applies any that
 * haven't been recorded in the `schema_migrations` table. Each migration
 * runs in a single transaction.
 *
 * Intentionally lightweight — once node-pg-migrate / sqitch / etc. is
 * picked up by WS-301, swap this out. Until then this is enough to wire
 * tests and a dev environment.
 */

import { readFile, readdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import pg from "pg";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MIGRATIONS_DIR = path.resolve(HERE, "../../migrations");

const SCHEMA_MIGRATIONS_DDL = `
  CREATE TABLE IF NOT EXISTS schema_migrations (
    name        text PRIMARY KEY,
    applied_at  timestamptz NOT NULL DEFAULT now()
  );
`;

export async function migrate(connectionString: string): Promise<string[]> {
  const client = new pg.Client({ connectionString });
  await client.connect();
  const applied: string[] = [];
  try {
    await client.query(SCHEMA_MIGRATIONS_DDL);

    const files = (await readdir(MIGRATIONS_DIR))
      .filter((f) => f.endsWith(".sql"))
      .sort();

    const { rows } = await client.query<{ name: string }>(
      "SELECT name FROM schema_migrations",
    );
    const seen = new Set(rows.map((r) => r.name));

    for (const file of files) {
      if (seen.has(file)) continue;
      const sql = await readFile(path.join(MIGRATIONS_DIR, file), "utf8");
      await client.query("BEGIN");
      try {
        await client.query(sql);
        await client.query(
          "INSERT INTO schema_migrations(name) VALUES ($1)",
          [file],
        );
        await client.query("COMMIT");
        applied.push(file);
      } catch (err) {
        await client.query("ROLLBACK");
        throw new Error(`migration ${file} failed: ${(err as Error).message}`);
      }
    }
  } finally {
    await client.end();
  }
  return applied;
}

// Allow `node migrate.ts` direct invocation.
if (import.meta.url === `file://${process.argv[1]}`) {
  const url = process.env.DATABASE_URL;
  if (!url) {
    console.error("DATABASE_URL is required");
    process.exit(1);
  }
  migrate(url).then(
    (applied) => {
      if (applied.length === 0) {
        console.log("No migrations to apply.");
      } else {
        console.log("Applied:", applied.join(", "));
      }
    },
    (err) => {
      console.error(err);
      process.exit(1);
    },
  );
}
