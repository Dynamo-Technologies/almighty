// Hackathon stubs. WS-504 builds the operator UI ahead of the agent runtime
// (WS-402/403/404) and live-state endpoints. Each call here is the wire-shape
// the renderer expects; the integration commit lives upstream of this file.

import type { CellRole } from "../auth/jwt";

export type EntityForce = "BLUE" | "RED" | "WHITE" | "NEUTRAL";

export interface EntitySummary {
  entity_id: string;
  display_name: string;
  type_subtype_ref: string;
  force_affiliation: EntityForce;
  position_lat_deg: number;
  position_lon_deg: number;
  position_alt_m: number;
}

export interface TurnSnapshot {
  current_turn: number;
  turn_state: "open" | "advancing";
  last_advanced_at: string | null;
}

export interface OrderRequest {
  tenant_id: string;
  scenario_id: string;
  cell_role: CellRole;
  officer: string;
  verb: string;
  payload: Record<string, unknown>;
}

export interface OrderResponse {
  accepted: boolean;
  event_id?: string;
  reason?: string;
}

const NASHVILLE = { lat: 36.18, lon: -86.78, alt: 200 };

function shift(lat: number, lon: number, dLatM: number, dLonM: number) {
  const M_PER_DLAT = 111_000;
  const M_PER_DLON = 111_000 * Math.cos((lat * Math.PI) / 180);
  return { lat: lat + dLatM / M_PER_DLAT, lon: lon + dLonM / M_PER_DLON };
}

function blueEntities(): EntitySummary[] {
  return [
    {
      entity_id: "00000000-0000-4000-8000-000000000001",
      display_name: "1-37 IN BN HQ",
      type_subtype_ref: "notional.ground.bct.battalion",
      force_affiliation: "BLUE",
      ...nashAt(0, 0),
    },
    {
      entity_id: "00000000-0000-4000-8000-000000000002",
      display_name: "A/1-37 (CO A)",
      type_subtype_ref: "notional.ground.bct.company",
      force_affiliation: "BLUE",
      ...nashAt(-1500, -800),
    },
    {
      entity_id: "00000000-0000-4000-8000-000000000003",
      display_name: "B/1-37 (CO B)",
      type_subtype_ref: "notional.ground.bct.company",
      force_affiliation: "BLUE",
      ...nashAt(-2000, 600),
    },
    {
      entity_id: "00000000-0000-4000-8000-000000000004",
      display_name: "C/1-37 (CO C)",
      type_subtype_ref: "notional.ground.bct.company",
      force_affiliation: "BLUE",
      ...nashAt(-1200, 1800),
    },
    {
      entity_id: "00000000-0000-4000-8000-000000000005",
      display_name: "FSC mortar section",
      type_subtype_ref: "notional.indirect.medium",
      force_affiliation: "BLUE",
      ...nashAt(-2500, -1500),
    },
  ];
}

function redEntities(): EntitySummary[] {
  return [
    {
      entity_id: "00000000-0000-4000-8000-000000000101",
      display_name: "12 Mech Bn (FWD)",
      type_subtype_ref: "notional.ground.opfor.bn",
      force_affiliation: "RED",
      ...nashAt(2200, 800),
    },
    {
      entity_id: "00000000-0000-4000-8000-000000000102",
      display_name: "Recon platoon",
      type_subtype_ref: "notional.ground.opfor.recon",
      force_affiliation: "RED",
      ...nashAt(800, 1500),
    },
    {
      entity_id: "00000000-0000-4000-8000-000000000103",
      display_name: "EW battery (jam)",
      type_subtype_ref: "notional.ew.peer.jammer",
      force_affiliation: "RED",
      ...nashAt(3000, -200),
    },
    {
      entity_id: "00000000-0000-4000-8000-000000000104",
      display_name: "UAS — Orlan-class",
      type_subtype_ref: "notional.uas.peer.tactical",
      force_affiliation: "RED",
      ...nashAt(2800, 2400),
    },
  ];
}

function nashAt(dLatM: number, dLonM: number): { position_lat_deg: number; position_lon_deg: number; position_alt_m: number } {
  const s = shift(NASHVILLE.lat, NASHVILLE.lon, dLatM, dLonM);
  return { position_lat_deg: s.lat, position_lon_deg: s.lon, position_alt_m: NASHVILLE.alt };
}

export async function fetchFriendlyEntities(force: EntityForce): Promise<EntitySummary[]> {
  // TODO WS-503/WS-104: replace with live query against the kernel/control-plane.
  await new Promise((r) => setTimeout(r, 50));
  return force === "BLUE" ? blueEntities() : redEntities();
}

export async function fetchTurnState(): Promise<TurnSnapshot> {
  // TODO WS-302: GET /tenants/:id/scenarios/:sid/turn (endpoint not yet exposed
  // in the public control-plane API; WS-302 ships /turns/advance only).
  await new Promise((r) => setTimeout(r, 50));
  return { current_turn: 3, turn_state: "open", last_advanced_at: "2026-04-25T22:14:00Z" };
}

export async function submitOrder(req: OrderRequest): Promise<OrderResponse> {
  // TODO WS-402/WS-403/WS-404: route into the agent runtime via the tenant's
  // turn-jobs queue. For v1 the renderer logs the order and pretends it was
  // accepted so the demo loop ("operator drafts → effect renders → kernel
  // commits") can be exercised against stubbed data.
  // eslint-disable-next-line no-console
  console.log("[WS-504 stub] order submitted", req);
  await new Promise((r) => setTimeout(r, 100));
  return { accepted: true, event_id: crypto.randomUUID() };
}
