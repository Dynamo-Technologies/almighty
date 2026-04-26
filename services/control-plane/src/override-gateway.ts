/**
 * WS-303 override gateway: policy CRUD, evaluation, and manual decisions.
 *
 * The kernel write path (currently routed via the WS-302 turn controller's
 * `applyOverrides` step) calls `evaluateEvent` for each agent-emitted event
 * before commit. The composability rule is fixed and well-known:
 *
 *   per-event > per-agent-per-turn > per-turn > default-review
 *
 * Lookup-chain semantics (first match wins):
 *
 *   1. Per-event:           any active policy with event_id = event.event_id
 *                           (current turn must satisfy TTL).
 *   2. Per-agent-per-turn:  any active policy with
 *                           (agent_entity_id = event.source_entity_id,
 *                            target_turn = event.turn).
 *                           TTL still applies (a stale policy is ignored).
 *   3. Per-turn:            any active policy with target_turn = event.turn
 *                           (TTL applies).
 *   4. None of the above:   default-review. The event holds in 'review-pending'
 *                           state until a white cell operator posts a manual
 *                           decision via POST /events/:eid/decision.
 *
 * Outcomes are recorded in `override_decisions` for the AAR (WS-506).
 *
 * TTL: a policy is valid in turn T iff
 *   created_in_turn ≤ T ≤ created_in_turn + ttl_turns.
 * ttl_turns = 0 means "single turn" — the turn it was authored in.
 */

import { randomUUID } from "node:crypto";
import type { Pool } from "./db.js";
import type {
  OverrideAction,
  OverrideDecisionOutcome,
  OverridePolicy,
  OverrideScope,
} from "./types.js";

// ---------- Custom error types (mapped to HTTP status by the routes layer) ----------

export class PolicyNotFoundError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PolicyNotFoundError";
  }
}

export class EventNotFoundError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EventNotFoundError";
  }
}

// ---------- Inputs / outputs ----------

export interface CreatePolicyInput {
  tenantId: string;
  scenarioId: string;
  scope: OverrideScope;
  action: OverrideAction;
  ttlTurns: number;
  rationale: string;
  createdBy: string;
  // Discrete polymorphic targets:
  eventId?: string;
  agentEntityId?: string;
  targetTurn?: number;
}

export interface ListPoliciesInput {
  tenantId: string;
  scenarioId: string;
  includeRevoked?: boolean;
}

export interface RevokePolicyInput {
  tenantId: string;
  scenarioId: string;
  policyId: string;
  revokedBy: string;
}

export interface EvaluateEventInput {
  tenantId: string;
  scenarioId: string;
  eventId: string;
  agentEntityId: string;
  turn: number;
}

export interface EvaluationResult {
  outcome: OverrideDecisionOutcome;
  policyId: string | null;
  matchedScope: OverrideScope | null;
  rationale: string;
  decisionId: string;
}

export interface ManualDecisionInput {
  tenantId: string;
  scenarioId: string;
  eventId: string;
  outcome: "review-approved" | "review-blocked";
  decidedBy: string;
  rationale: string;
}

// ---------- Policy CRUD ----------

export async function createPolicy(pool: Pool, input: CreatePolicyInput): Promise<OverridePolicy> {
  // The current_turn for the scenario is the "created_in_turn" stamp.
  const turnRow = await pool.query<{ current_turn: number }>(
    `SELECT current_turn FROM scenarios
      WHERE tenant_id = $1 AND scenario_id = $2`,
    [input.tenantId, input.scenarioId],
  );
  if (turnRow.rowCount === 0) {
    throw new EventNotFoundError(
      `scenario ${input.scenarioId} not found in tenant ${input.tenantId}`,
    );
  }
  const createdInTurn = turnRow.rows[0]!.current_turn;

  const result = await pool.query<OverridePolicy>(
    `INSERT INTO override_policies (
       tenant_id, scenario_id, scope,
       event_id, agent_entity_id, target_turn,
       action, ttl_turns, created_in_turn,
       rationale, created_by
     ) VALUES (
       $1, $2, $3,
       $4, $5, $6,
       $7, $8, $9,
       $10, $11
     )
     RETURNING *`,
    [
      input.tenantId,
      input.scenarioId,
      input.scope,
      input.eventId ?? null,
      input.agentEntityId ?? null,
      input.targetTurn ?? null,
      input.action,
      input.ttlTurns,
      createdInTurn,
      input.rationale,
      input.createdBy,
    ],
  );
  return result.rows[0]!;
}

export async function listPolicies(
  pool: Pool,
  input: ListPoliciesInput,
): Promise<OverridePolicy[]> {
  const sql = input.includeRevoked
    ? `SELECT * FROM override_policies
        WHERE tenant_id = $1 AND scenario_id = $2
        ORDER BY created_at DESC`
    : `SELECT * FROM override_policies
        WHERE tenant_id = $1 AND scenario_id = $2 AND status = 'active'
        ORDER BY created_at DESC`;
  const result = await pool.query<OverridePolicy>(sql, [input.tenantId, input.scenarioId]);
  return result.rows;
}

export async function revokePolicy(pool: Pool, input: RevokePolicyInput): Promise<OverridePolicy> {
  const result = await pool.query<OverridePolicy>(
    `UPDATE override_policies
        SET status = 'revoked',
            updated_at = now()
      WHERE tenant_id = $1 AND scenario_id = $2 AND policy_id = $3 AND status = 'active'
      RETURNING *`,
    [input.tenantId, input.scenarioId, input.policyId],
  );
  if (result.rowCount === 0) {
    throw new PolicyNotFoundError(
      `policy ${input.policyId} not found, already revoked, or not in scenario ${input.scenarioId}`,
    );
  }
  return result.rows[0]!;
}

// ---------- Evaluation ----------

const ACTION_TO_OUTCOME: Record<OverrideAction, OverrideDecisionOutcome> = {
  "auto-approve": "auto-approve",
  "auto-block": "auto-block",
  review: "review-pending",
};

/**
 * Look up the highest-priority active policy that matches an event,
 * respecting TTL. Returns null when no policy applies (the caller maps
 * that to default-review).
 *
 * The query joins the per-scope filtered indexes via UNION ALL so we get
 * the priority chain in one round-trip. PRIORITY column in the SELECT
 * encodes the lookup chain (1 = per-event, 2 = per-agent-per-turn, 3 = per-turn).
 */
async function findMatchingPolicy(
  pool: Pool,
  input: EvaluateEventInput,
): Promise<OverridePolicy | null> {
  const result = await pool.query<OverridePolicy & { priority: number }>(
    `WITH candidates AS (
       SELECT 1 AS priority, *
         FROM override_policies
        WHERE tenant_id = $1
          AND scenario_id = $2
          AND status = 'active'
          AND scope = 'per-event'
          AND event_id = $3
          AND $5 BETWEEN created_in_turn AND created_in_turn + ttl_turns
       UNION ALL
       SELECT 2 AS priority, *
         FROM override_policies
        WHERE tenant_id = $1
          AND scenario_id = $2
          AND status = 'active'
          AND scope = 'per-agent-per-turn'
          AND agent_entity_id = $4
          AND target_turn = $5
          AND $5 BETWEEN created_in_turn AND created_in_turn + ttl_turns
       UNION ALL
       SELECT 3 AS priority, *
         FROM override_policies
        WHERE tenant_id = $1
          AND scenario_id = $2
          AND status = 'active'
          AND scope = 'per-turn'
          AND target_turn = $5
          AND $5 BETWEEN created_in_turn AND created_in_turn + ttl_turns
     )
     SELECT * FROM candidates
      ORDER BY priority ASC, created_at DESC
      LIMIT 1`,
    [input.tenantId, input.scenarioId, input.eventId, input.agentEntityId, input.turn],
  );
  if (result.rowCount === 0) return null;
  // Strip the synthetic priority column; the remaining shape matches OverridePolicy.
  const { priority: _priority, ...policy } = result.rows[0]!;
  return policy as OverridePolicy;
}

export async function evaluateEvent(
  pool: Pool,
  input: EvaluateEventInput,
): Promise<EvaluationResult> {
  const policy = await findMatchingPolicy(pool, input);
  const outcome: OverrideDecisionOutcome = policy
    ? ACTION_TO_OUTCOME[policy.action]
    : "default-review";

  const decisionId = randomUUID();
  await pool.query(
    `INSERT INTO override_decisions (
       decision_id, tenant_id, scenario_id, event_id, turn,
       outcome, policy_id, matched_scope, decided_by, rationale
     ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NULL, $9)`,
    [
      decisionId,
      input.tenantId,
      input.scenarioId,
      input.eventId,
      input.turn,
      outcome,
      policy?.policy_id ?? null,
      policy?.scope ?? null,
      policy?.rationale ?? "",
    ],
  );

  return {
    outcome,
    policyId: policy?.policy_id ?? null,
    matchedScope: policy?.scope ?? null,
    rationale: policy?.rationale ?? "",
    decisionId,
  };
}

// ---------- Manual decision (review path) ----------

export async function manualDecision(
  pool: Pool,
  input: ManualDecisionInput,
): Promise<EvaluationResult> {
  // Confirm the event exists in this (tenant, scenario). The events table
  // is shared across the namespace; we don't need its full shape — just
  // its existence + turn.
  const eventRow = await pool.query<{ turn: number }>(
    `SELECT turn FROM events
      WHERE tenant_id = $1 AND scenario_id = $2 AND event_id = $3`,
    [input.tenantId, input.scenarioId, input.eventId],
  );
  if (eventRow.rowCount === 0) {
    throw new EventNotFoundError(
      `event ${input.eventId} not found in tenant ${input.tenantId}, scenario ${input.scenarioId}`,
    );
  }
  const turn = eventRow.rows[0]!.turn;

  const decisionId = randomUUID();
  await pool.query(
    `INSERT INTO override_decisions (
       decision_id, tenant_id, scenario_id, event_id, turn,
       outcome, policy_id, matched_scope, decided_by, rationale
     ) VALUES ($1, $2, $3, $4, $5, $6, NULL, NULL, $7, $8)`,
    [
      decisionId,
      input.tenantId,
      input.scenarioId,
      input.eventId,
      turn,
      input.outcome,
      input.decidedBy,
      input.rationale,
    ],
  );

  return {
    outcome: input.outcome,
    policyId: null,
    matchedScope: null,
    rationale: input.rationale,
    decisionId,
  };
}

// ---------- Turn-controller integration (replaces stub) ----------

/**
 * Called by the WS-302 turn controller as part of the turn-advance flow.
 * In v1 there are no in-flight uncommitted events to evaluate — the
 * agent runtime (WS-401) hasn't shipped yet. Once WS-401 lands, this
 * function will iterate the agent commit queue and call evaluateEvent
 * per event.
 *
 * For v1 it returns processedEvents=0 so the turn controller's contract
 * stays stable. The interception point is here, ready to populate.
 */
export async function applyOverrides(
  _pool: Pool,
  input: { tenantId: string; scenarioId: string; turn: number },
): Promise<{ ok: true; processedEvents: number }> {
  void input;
  // TODO WS-401: once the agent-runtime harness lands, drain the
  // tenant-scoped commit queue here, calling evaluateEvent per event
  // and then committing only events whose outcome is auto-approve or
  // review-approved.
  return { ok: true, processedEvents: 0 };
}
