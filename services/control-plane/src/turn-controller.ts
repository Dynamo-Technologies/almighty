/**
 * WS-302 turn advancement workflow.
 *
 * Six steps per the issue prompt:
 *   1. Lock current turn — set scenarios.turn_state = 'advancing'.
 *   2. Trigger between-turn agent execution — WS-401 stub.
 *   3. Apply overrides — WS-303 stub.
 *   4. Snapshot state — write to turn_snapshots.
 *   5. Increment current_turn, set turn_state = 'open'.
 *   6. Emit turn_state event onto WebSocket fan-out — WS-304 stub.
 *
 * Concurrency: the lock is acquired via SELECT … FOR UPDATE inside a
 * transaction so concurrent advance requests serialize. If the scenario
 * is already in turn_state='advancing' when the request lands, the call
 * raises TurnAdvanceConflictError; the route layer maps that to HTTP 409.
 */

import type { Pool } from "./db.js";
import { runBetweenTurnAgents } from "./stubs/agent-runtime.js";
import { applyOverrides } from "./stubs/override-gateway.js";
import { publishTurnState } from "./stubs/websocket-fanout.js";

export interface AdvanceTurnInput {
  tenantId: string;
  scenarioId: string;
}

export interface AdvanceTurnResult {
  tenantId: string;
  scenarioId: string;
  closedTurn: number;
  newTurn: number;
  snapshotId: string;
  agentRuntimeMs: number;
}

export class TurnAdvanceConflictError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TurnAdvanceConflictError";
  }
}

export class ScenarioNotFoundError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ScenarioNotFoundError";
  }
}

const SNAPSHOT_RECENT_EVENTS_LIMIT = 1000;

export async function advanceTurn(
  pool: Pool,
  input: AdvanceTurnInput,
): Promise<AdvanceTurnResult> {
  const { tenantId, scenarioId } = input;
  const client = await pool.connect();
  let closedTurn = 0;
  let newTurn = 0;
  let snapshotId = "";

  try {
    // ---- Step 1: lock current turn ----
    await client.query("BEGIN");

    const lockResult = await client.query<{
      current_turn: number;
      turn_state: string;
    }>(
      `SELECT current_turn, turn_state
         FROM scenarios
        WHERE tenant_id = $1 AND scenario_id = $2
        FOR UPDATE`,
      [tenantId, scenarioId],
    );

    if (lockResult.rowCount === 0) {
      await client.query("ROLLBACK");
      throw new ScenarioNotFoundError(
        `scenario ${scenarioId} not found in tenant ${tenantId}`,
      );
    }

    const row = lockResult.rows[0]!;
    if (row.turn_state === "advancing") {
      await client.query("ROLLBACK");
      throw new TurnAdvanceConflictError(
        `scenario ${scenarioId} already advancing; concurrent request rejected`,
      );
    }

    closedTurn = row.current_turn;

    await client.query(
      `UPDATE scenarios
          SET turn_state = 'advancing'
        WHERE tenant_id = $1 AND scenario_id = $2`,
      [tenantId, scenarioId],
    );
    await client.query("COMMIT");

    // ---- Step 2: between-turn agents (stubbed) ----
    const agentResult = await runBetweenTurnAgents({
      tenantId,
      scenarioId,
      turn: closedTurn,
    });

    // ---- Step 3: apply overrides (stubbed) ----
    await applyOverrides({ tenantId, scenarioId, turn: closedTurn });

    // ---- Step 4: snapshot state ----
    // Pull entities + last N events for the closing turn. Snapshot row +
    // current_turn bump in step 5 commit atomically.
    await client.query("BEGIN");

    const entitiesResult = await client.query(
      `SELECT *
         FROM entities
        WHERE tenant_id = $1 AND scenario_id = $2`,
      [tenantId, scenarioId],
    );

    const eventsResult = await client.query(
      `SELECT *
         FROM events
        WHERE tenant_id = $1 AND scenario_id = $2 AND turn = $3
        ORDER BY ts DESC
        LIMIT $4`,
      [tenantId, scenarioId, closedTurn, SNAPSHOT_RECENT_EVENTS_LIMIT],
    );

    const snapshotJson = {
      entities: entitiesResult.rows,
      events: eventsResult.rows,
      meta: {
        closed_turn: closedTurn,
        snapshot_event_limit: SNAPSHOT_RECENT_EVENTS_LIMIT,
        agent_runtime_ms: agentResult.durationMs,
      },
    };

    const snapshotInsert = await client.query<{ snapshot_id: string }>(
      `INSERT INTO turn_snapshots (tenant_id, scenario_id, turn, snapshot_json)
            VALUES ($1, $2, $3, $4)
         RETURNING snapshot_id`,
      [tenantId, scenarioId, closedTurn, snapshotJson],
    );
    snapshotId = snapshotInsert.rows[0]!.snapshot_id;

    // ---- Step 5: open next turn ----
    newTurn = closedTurn + 1;
    await client.query(
      `UPDATE scenarios
          SET current_turn = $3,
              turn_state   = 'open'
        WHERE tenant_id = $1 AND scenario_id = $2`,
      [tenantId, scenarioId, newTurn],
    );

    await client.query("COMMIT");

    // ---- Step 6: emit turn_state event (stubbed) ----
    await publishTurnState({
      tenantId,
      scenarioId,
      turn: newTurn,
      state: "open",
      notifiedAt: new Date().toISOString(),
    });

    return {
      tenantId,
      scenarioId,
      closedTurn,
      newTurn,
      snapshotId,
      agentRuntimeMs: agentResult.durationMs,
    };
  } catch (err) {
    // If we crashed after step 1 left turn_state='advancing', revert it so
    // a retry isn't blocked. v1 doesn't track retry counters; the white
    // cell is expected to inspect logs and retry.
    try {
      await client.query("ROLLBACK").catch(() => {});
      await client.query(
        `UPDATE scenarios
            SET turn_state = 'open'
          WHERE tenant_id = $1 AND scenario_id = $2 AND turn_state = 'advancing'`,
        [tenantId, scenarioId],
      );
    } catch {
      // Swallow secondary errors — the original is the one the caller cares about.
    }
    throw err;
  } finally {
    client.release();
  }
}
