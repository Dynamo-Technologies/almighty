/**
 * Real between-turn agent runner.
 *
 * Replaces the WS-401 stub for the hackathon demo. POSTs to the FastAPI
 * shim on spark-763d (over Tailscale) and writes returned events into
 * the events table so the AAR / EXCON consoles can render them. The
 * shim parallelizes blue + red crews; the response is a flat list of
 * events, each carrying causal_predecessors that the LLM-driven roles
 * auto-linked to the situation-report parents.
 *
 * Production path (when WS-401 ships its real Celery harness) replaces
 * this with `enqueue_turn(...)` + a Celery worker. For the demo the
 * direct HTTP call is simpler and the tradeoff is fine — we own both
 * sides and the call is bounded.
 */

import type { Pool } from "../db.js";
import { loadEnv } from "../config.js";

interface AgentEvent {
  event_id: string;
  verb: string;
  officer_type: "SENSOR" | "EFFECTOR" | "MOVER" | "COMMUNICATOR" | "COMMANDER";
  source_entity_id: string | null;
  causal_predecessors: string[];
  side: string;
  step: string;
  validator: string;
  llm_driven?: boolean;
}

interface RunTurnResponse {
  turn: number;
  blue_duration_ms: number;
  red_duration_ms: number;
  events: AgentEvent[];
}

const FALLBACK_SOURCE_ENTITY_ID = "00000000-0000-4d00-8000-0000000000ff";

export async function runBetweenTurnAgents(
  input: { tenantId: string; scenarioId: string; turn: number },
  pool?: Pool,
): Promise<{ ok: true; durationMs: number; eventsCommitted: number }> {
  const startedAt = Date.now();
  const env = loadEnv();
  const sparkUrl = env.SPARK_WORKER_URL.replace(/\/$/, "");

  // The turn-controller passes the CLOSING turn (input.turn). The events
  // produced by the agents stamp the NEW turn so they sort with what the
  // user just clicked "Advance to". `current_turn` in the scenarios row
  // is incremented separately by the turn-controller after this returns.
  const newTurn = input.turn + 1;

  const res = await fetch(`${sparkUrl}/run-turn`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      tenant_id: input.tenantId,
      scenario_id: input.scenarioId,
      turn: newTurn,
    }),
    // 3-minute upper bound — typical run is 30-60s with the bigger 31B
    // dominating; failure should surface fast on stage.
    signal: AbortSignal.timeout(180_000),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "(no body)");
    throw new Error(
      `spark worker /run-turn returned ${res.status} ${res.statusText}: ${body.slice(0, 500)}`,
    );
  }

  const body = (await res.json()) as RunTurnResponse;
  let eventsCommitted = 0;

  if (pool && body.events.length > 0) {
    const client = await pool.connect();
    try {
      for (const e of body.events) {
        // ON CONFLICT DO NOTHING — re-running a turn during testing
        // shouldn't double-insert and should keep the original
        // causal_predecessors. event_id is the PK.
        await client.query(
          `INSERT INTO events (
              event_id, tenant_id, scenario_id, turn,
              source_officer_type, source_entity_id,
              action_verb, payload, causal_predecessors, ts
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::uuid[], NOW())
            ON CONFLICT (event_id) DO NOTHING`,
          [
            e.event_id,
            input.tenantId,
            input.scenarioId,
            newTurn,
            e.officer_type,
            e.source_entity_id ?? FALLBACK_SOURCE_ENTITY_ID,
            e.verb,
            // Worker doesn't surface payload (out of scope for the demo).
            // Stamp the side + step so the renderer can group/show it.
            JSON.stringify({ side: e.side, step: e.step, llm_driven: !!e.llm_driven }),
            e.causal_predecessors ?? [],
          ],
        );
        eventsCommitted += 1;
      }
    } finally {
      client.release();
    }
  }

  return {
    ok: true,
    durationMs: Date.now() - startedAt,
    eventsCommitted,
  };
}
