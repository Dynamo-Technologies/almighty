// AAR (after-action review) data sources. Events come from the real
// control-plane endpoint added in WS-506. Override decisions are still
// synthetic — once WS-303 starts emitting `override_decision`-tagged events
// into the events table, derive them from the same /events fetch.

import { getStoredToken } from "../auth/jwt";

export interface DagEvent {
  event_id: string;
  tenant_id: string;
  scenario_id: string;
  turn: number;
  source_officer_type: "SENSOR" | "EFFECTOR" | "MOVER" | "COMMUNICATOR" | "COMMANDER";
  source_entity_id: string;
  action_verb: string;
  payload: Record<string, unknown>;
  causal_predecessors: string[];
  ts: string; // ISO-8601
  created_at: string;
}

export interface OverrideDecision {
  decision_id: string;
  ts: string;
  scope: "per-event" | "per-agent-per-turn" | "per-turn";
  target_id: string;
  action: "review" | "auto-approve" | "auto-block";
  rationale: string;
  decided_by: string;
}

export interface AarEnvelope {
  scenario: { tenant_id: string; scenario_id: string; replay_source: string };
  events: DagEvent[];
  override_decisions: OverrideDecision[];
  generated_at: string;
}

const CONTROL_PLANE_BASE = (() => {
  if (typeof window === "undefined") return "http://localhost:4000";
  // Vite proxies aren't configured; for v1 the operator points the renderer at
  // a known control-plane URL via env. Default localhost for dev.
  return import.meta.env?.VITE_CONTROL_PLANE_URL ?? "http://localhost:4000";
})();

export async function fetchEvents(
  tenantId: string,
  scenarioId: string,
  opts?: { since_ts?: string; until_ts?: string; limit?: number },
): Promise<DagEvent[]> {
  const token = getStoredToken();
  if (!token) throw new Error("no JWT in localStorage; set one via DevTokenForm");

  const url = new URL(`${CONTROL_PLANE_BASE}/tenants/${tenantId}/scenarios/${scenarioId}/events`);
  if (opts?.since_ts) url.searchParams.set("since_ts", opts.since_ts);
  if (opts?.until_ts) url.searchParams.set("until_ts", opts.until_ts);
  if (opts?.limit) url.searchParams.set("limit", String(opts.limit));

  const res = await fetch(url.toString(), {
    headers: { authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error(`GET /events → ${res.status} ${res.statusText}`);
  }
  const body = (await res.json()) as { events: DagEvent[]; count: number };
  return body.events;
}

/**
 * Fixture event log for demo when /events returns empty. Mirrors the
 * Nashville vignette's tactical sequence (per WS-204) so the AAR has
 * something to scrub through before agents run for real.
 */
export function fixtureEvents(tenantId: string, scenarioId: string): DagEvent[] {
  const t = (offsetSec: number): string =>
    new Date(Date.parse("2026-04-25T22:00:00Z") + offsetSec * 1000).toISOString();
  const E = "44444444-4444-4444-8444-440000000000";
  const mk = (
    n: number,
    turn: number,
    ts: string,
    officer: DagEvent["source_officer_type"],
    verb: string,
    payload: Record<string, unknown>,
  ): DagEvent => ({
    event_id: `fixture-${String(n).padStart(4, "0")}`,
    tenant_id: tenantId,
    scenario_id: scenarioId,
    turn,
    source_officer_type: officer,
    source_entity_id: E,
    action_verb: verb,
    payload,
    causal_predecessors: [],
    ts,
    created_at: ts,
  });

  return [
    mk(1, 1, t(0),    "MOVER",        "move_to",     { target_lat_deg: 36.20, target_lon_deg: -86.78, target_alt_m: 500 }),
    mk(2, 1, t(60),   "COMMUNICATOR", "jam",         { center_lat_deg: 36.18, center_lon_deg: -86.81, radius_m: 2000, power_w: 600, band: "VHF" }),
    mk(3, 2, t(120),  "SENSOR",       "detect",      { target_entity_id: E, modality: "RADAR", confidence: 0.82, range_m: 12000 }),
    mk(4, 2, t(180),  "EFFECTOR",     "engage",      { target_lat_deg: 36.198, target_lon_deg: -86.762, weapon_system: "notional.indirect.medium", volume_count: 4 }),
    mk(5, 3, t(240),  "SENSOR",       "classify",    { track_id: "trk-001", classification_label: "wheeled-EW", confidence: 0.74, dwell_s: 8 }),
    mk(6, 3, t(300),  "EFFECTOR",     "destroy",     { target_entity_id: E, weapon_system: "notional.indirect.medium", volume_count: 8, justification: "Confirmed EW emitter; CARVER 21." }),
    mk(7, 4, t(360),  "COMMANDER",    "report",      { report_type: "SITREP", to_echelon: "BRIGADE", report_payload: { summary: "EW threat neutralized; phase line PL Cumberland secured." } }),
  ];
}

export function fixtureOverrideDecisions(): OverrideDecision[] {
  const t = (offsetSec: number): string =>
    new Date(Date.parse("2026-04-25T22:00:00Z") + offsetSec * 1000).toISOString();
  return [
    {
      decision_id: "ovr-decision-0001",
      ts: t(305),
      scope: "per-event",
      target_id: "fixture-0006",
      action: "review",
      rationale: "Effector.destroy on EW battery — held for white-cell adjudication; CARVER score reviewed and approved.",
      decided_by: "white@demo",
    },
    {
      decision_id: "ovr-decision-0002",
      ts: t(125),
      scope: "per-turn",
      target_id: "2",
      action: "auto-approve",
      rationale: "Routine sensor + mover traffic for turn 2 — pre-cleared.",
      decided_by: "white@demo",
    },
  ];
}

export function buildAarEnvelope(opts: {
  tenantId: string;
  scenarioId: string;
  events: DagEvent[];
  overrideDecisions: OverrideDecision[];
  replaySource: string;
}): AarEnvelope {
  return {
    scenario: { tenant_id: opts.tenantId, scenario_id: opts.scenarioId, replay_source: opts.replaySource },
    events: opts.events,
    override_decisions: opts.overrideDecisions,
    generated_at: new Date().toISOString(),
  };
}

/**
 * v1 export: triggers a browser download of the AAR JSON bundle. Spec calls
 * for an S3 upload to `s3://almighty-${tenant_id}-${env}/aar/${scenario_id}/`
 * and a generated PDF — both deferred (no S3 SDK in the renderer; PDF via
 * browser print is the v1 workaround).
 */
export function downloadAarBundle(envelope: AarEnvelope): void {
  const blob = new Blob([JSON.stringify(envelope, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `aar-${envelope.scenario.scenario_id}-${envelope.generated_at.replace(/[:.]/g, "-")}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
