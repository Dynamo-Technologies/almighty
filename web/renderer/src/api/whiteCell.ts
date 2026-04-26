// White-cell API surface. v1 mocks. The wire shapes match what
// services/control-plane/ exposes (or will expose) so swapping the bodies
// to real fetch() calls is a one-commit job per function.

export type OverrideScope = "per-event" | "per-agent-per-turn" | "per-turn";
export type OverrideAction = "review" | "auto-approve" | "auto-block";

export interface OverridePolicy {
  policy_id: string;
  scope: OverrideScope;
  target_id: string;
  action: OverrideAction;
  ttl_turns: number;
  rationale: string;
  created_at: string;
}

export interface PendingReviewItem {
  event_id: string;
  source_entity_id: string;
  source_entity_name: string;
  agent_id: string;
  capability_profile_ref: string;
  proposed_verb: string;
  proposed_payload: Record<string, unknown>;
  validator_result: "accepted" | "rejected" | "review";
  human_required: boolean;
  arrived_at: string;
}

export interface CapabilityProfile {
  profile_id: string;
  version: number;
  display_name: string;
  /** Full profile body. Keys defined in WS-106; renderer treats as opaque JSON. */
  body: Record<string, unknown>;
}

// ---------- Turn advancement (WS-302) ----------

export async function advanceTurn(): Promise<{ next_turn: number; snapshot_at: string }> {
  // TODO WS-302 wiring: POST /tenants/:id/scenarios/:sid/turns/advance with
  // the white-cell JWT. Endpoint returns the new turn number + snapshot ts.
  await new Promise((r) => setTimeout(r, 600));
  const snapshot_at = new Date().toISOString();
  // eslint-disable-next-line no-console
  console.log("[WS-505 stub] advance turn ←", snapshot_at);
  return { next_turn: NEXT_TURN++, snapshot_at };
}

let NEXT_TURN = 4;

// ---------- Override policies (WS-303) ----------

const POLICIES: OverridePolicy[] = [
  {
    policy_id: "ovr-0001",
    scope: "per-turn",
    target_id: "3",
    action: "auto-approve",
    ttl_turns: 1,
    rationale: "Routine sensor / mover traffic for turn 3 — pre-cleared by white cell.",
    created_at: "2026-04-25T22:00:00Z",
  },
  {
    policy_id: "ovr-0002",
    scope: "per-event",
    target_id: "evt-destroy-*",
    action: "review",
    ttl_turns: 0,
    rationale: "Always review Effector.destroy events.",
    created_at: "2026-04-25T22:01:00Z",
  },
];

export async function listOverridePolicies(): Promise<OverridePolicy[]> {
  await new Promise((r) => setTimeout(r, 80));
  return [...POLICIES];
}

export async function createOverridePolicy(p: Omit<OverridePolicy, "policy_id" | "created_at">): Promise<OverridePolicy> {
  // TODO WS-303 wiring: POST /tenants/:id/scenarios/:sid/overrides
  await new Promise((r) => setTimeout(r, 150));
  const created: OverridePolicy = {
    ...p,
    policy_id: `ovr-${crypto.randomUUID().slice(0, 4)}`,
    created_at: new Date().toISOString(),
  };
  POLICIES.unshift(created);
  // eslint-disable-next-line no-console
  console.log("[WS-505 stub] create policy ←", created);
  return created;
}

export async function revokeOverridePolicy(policy_id: string): Promise<void> {
  // TODO WS-303 wiring: DELETE /tenants/:id/scenarios/:sid/overrides/:oid
  await new Promise((r) => setTimeout(r, 120));
  const idx = POLICIES.findIndex((p) => p.policy_id === policy_id);
  if (idx >= 0) POLICIES.splice(idx, 1);
  // eslint-disable-next-line no-console
  console.log("[WS-505 stub] revoke policy ←", policy_id);
}

// ---------- Capability profiles (WS-107) ----------

const PROFILES: CapabilityProfile[] = [
  {
    profile_id: "00000000-bbbb-0001-0000-000000000001",
    version: 1,
    display_name: "Notional US BCT — battalion",
    body: {
      profile_id: "00000000-bbbb-0001-0000-000000000001",
      version: 1,
      display_name: "Notional US BCT — battalion",
      force_affiliation: "BLUE",
      effect_parameter_ranges: {
        radar_fan: { sweep_arc_deg: { min: 10, max: 360 }, range_m: { min: 500, max: 50000 } },
      },
      // ... other keys per WS-106. Truncated for the editor demo.
    },
  },
  {
    profile_id: "00000000-bbbb-0002-0000-000000000002",
    version: 1,
    display_name: "Notional peer adversary",
    body: {
      profile_id: "00000000-bbbb-0002-0000-000000000002",
      version: 1,
      display_name: "Notional peer adversary",
      force_affiliation: "RED",
      effect_parameter_ranges: {
        jamming_circle: { radius_m: { min: 200, max: 8000 }, power_w: { min: 50, max: 1500 } },
      },
    },
  },
];

export async function listProfiles(): Promise<CapabilityProfile[]> {
  await new Promise((r) => setTimeout(r, 80));
  return PROFILES.map((p) => ({ ...p, body: { ...p.body } }));
}

export async function saveProfile(p: CapabilityProfile): Promise<CapabilityProfile> {
  // TODO WS-107 wiring: PATCH /tenants/:id/scenarios/:sid/profiles/:pid
  // Profile authoring is pre-scenario only — the control plane should reject
  // edits once turn >= 1. For v1 we surface the "locked" state in the UI but
  // still accept the call so the demo loop is exercisable.
  await new Promise((r) => setTimeout(r, 200));
  const idx = PROFILES.findIndex((q) => q.profile_id === p.profile_id);
  if (idx >= 0) PROFILES[idx] = p;
  // eslint-disable-next-line no-console
  console.log("[WS-505 stub] save profile ←", p.profile_id);
  return p;
}

// ---------- Review queue (WS-303) ----------

const PENDING: PendingReviewItem[] = [
  {
    event_id: "evt-0042",
    source_entity_id: "00000000-0000-4000-8000-000000000005",
    source_entity_name: "FSC mortar section",
    agent_id: "blue.s3",
    capability_profile_ref: "00000000-bbbb-0001-0000-000000000001@1",
    proposed_verb: "engage",
    proposed_payload: {
      target_lat_deg: 36.198,
      target_lon_deg: -86.762,
      weapon_system: "notional.indirect.medium",
      volume_count: 4,
      intent: "NEUTRALIZE",
    },
    validator_result: "review",
    human_required: false,
    arrived_at: "2026-04-25T22:14:32Z",
  },
  {
    event_id: "evt-0043",
    source_entity_id: "00000000-0000-4000-8000-000000000002",
    source_entity_name: "A/1-37 (CO A)",
    agent_id: "blue.co_a",
    capability_profile_ref: "00000000-bbbb-0001-0000-000000000001@1",
    proposed_verb: "destroy",
    proposed_payload: {
      target_entity_id: "00000000-0000-4000-8000-000000000103",
      weapon_system: "notional.indirect.medium",
      volume_count: 8,
      justification: "Confirmed EW emitter degrading 1-37 comms; CARVER score 21.",
    },
    validator_result: "review",
    human_required: true,
    arrived_at: "2026-04-25T22:15:01Z",
  },
];

export type ReviewDecision = "approve" | "block" | "edit-and-approve" | "inject-manual";

export async function listPendingReview(): Promise<PendingReviewItem[]> {
  await new Promise((r) => setTimeout(r, 80));
  return [...PENDING];
}

export async function decideReview(event_id: string, decision: ReviewDecision): Promise<void> {
  // TODO WS-303 wiring: POST /tenants/:id/scenarios/:sid/events/:eid/decision
  await new Promise((r) => setTimeout(r, 120));
  const idx = PENDING.findIndex((p) => p.event_id === event_id);
  if (idx >= 0) PENDING.splice(idx, 1);
  // eslint-disable-next-line no-console
  console.log("[WS-505 stub] decide", event_id, "→", decision);
}
