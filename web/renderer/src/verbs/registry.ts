// Verb registry derived from docs/schema/officer-interfaces.md (WS-105).
// Field names match the doc 1:1 — they're the keys that ship in the
// PyRapide event payload.

export type OfficerType = "Sensor" | "Effector" | "Mover" | "Communicator" | "Commander";

export type VerbFieldType = "number" | "string" | "uuid" | "bool" | "enum" | "object";

export interface VerbField {
  name: string;
  type: VerbFieldType;
  units?: string;
  required: boolean;
  enumValues?: readonly string[];
  min?: number;
  max?: number;
  description?: string;
}

export interface VerbSpec {
  verb: string;
  officer: OfficerType;
  fields: readonly VerbField[];
  /** Effect family from WS-108 — used for the on-map ghost preview. */
  spatialArtifact?:
    | "ew_cone"
    | "uas_corridor"
    | "radar_fan"
    | "jamming_circle"
    | "satellite_swath"
    | "indirect_fire_arc"
    | "ir_plume"
    | "masint_cell"
    | "keyhole_footprint";
}

export const VERBS: readonly VerbSpec[] = [
  // ------- Sensor -------
  {
    verb: "detect",
    officer: "Sensor",
    fields: [
      { name: "target_entity_id", type: "uuid", required: true },
      {
        name: "modality",
        type: "enum",
        required: true,
        enumValues: ["EO_IR", "RF", "RADAR", "ACOUSTIC", "SEISMIC", "MASINT_MULTI"],
      },
      { name: "confidence", type: "number", required: true, min: 0, max: 1 },
      { name: "range_m", type: "number", units: "m", required: true },
    ],
  },
  {
    verb: "track",
    officer: "Sensor",
    fields: [
      { name: "target_entity_id", type: "uuid", required: true },
      { name: "track_id", type: "uuid", required: false },
      { name: "update_rate_hz", type: "number", units: "Hz", required: true },
      { name: "lifetime_s", type: "number", units: "s", required: false },
    ],
  },
  {
    verb: "classify",
    officer: "Sensor",
    spatialArtifact: "keyhole_footprint",
    fields: [
      { name: "track_id", type: "uuid", required: true },
      { name: "classification_label", type: "string", required: true },
      { name: "confidence", type: "number", required: true, min: 0, max: 1 },
      { name: "dwell_s", type: "number", units: "s", required: true },
    ],
  },
  {
    verb: "lose_track",
    officer: "Sensor",
    fields: [
      { name: "track_id", type: "uuid", required: true },
      {
        name: "reason",
        type: "enum",
        required: true,
        enumValues: ["OUT_OF_RANGE", "OCCLUDED", "JAMMED", "DECONFLICTED", "DESTROYED_TARGET", "OPERATOR_REQUEST"],
      },
    ],
  },
  // ------- Effector -------
  {
    verb: "engage",
    officer: "Effector",
    spatialArtifact: "indirect_fire_arc",
    fields: [
      { name: "target_lat_deg", type: "number", units: "deg", required: true, min: -90, max: 90 },
      { name: "target_lon_deg", type: "number", units: "deg", required: true, min: -180, max: 180 },
      { name: "target_alt_m", type: "number", units: "m", required: true },
      { name: "weapon_system", type: "string", required: true },
      { name: "volume_count", type: "number", required: true, min: 1 },
      {
        name: "intent",
        type: "enum",
        required: false,
        enumValues: ["NEUTRALIZE", "SUPPRESS_AND_HOLD", "MARKER"],
      },
    ],
  },
  {
    verb: "suppress",
    officer: "Effector",
    spatialArtifact: "indirect_fire_arc",
    fields: [
      { name: "target_lat_deg", type: "number", units: "deg", required: true, min: -90, max: 90 },
      { name: "target_lon_deg", type: "number", units: "deg", required: true, min: -180, max: 180 },
      { name: "weapon_system", type: "string", required: true },
      { name: "duration_s", type: "number", units: "s", required: true },
      { name: "rate_per_min", type: "number", units: "/min", required: true },
    ],
  },
  {
    verb: "destroy",
    officer: "Effector",
    spatialArtifact: "indirect_fire_arc",
    fields: [
      { name: "target_entity_id", type: "uuid", required: true },
      { name: "weapon_system", type: "string", required: true },
      { name: "volume_count", type: "number", required: true, min: 1 },
      { name: "justification", type: "string", required: true },
    ],
  },
  {
    verb: "disable",
    officer: "Effector",
    fields: [
      { name: "target_entity_id", type: "uuid", required: true },
      {
        name: "method",
        type: "enum",
        required: true,
        enumValues: ["KINETIC", "EW", "CYBER"],
      },
      { name: "weapon_system", type: "string", required: true },
      { name: "intensity", type: "number", required: false },
    ],
  },
  // ------- Mover -------
  {
    verb: "move_to",
    officer: "Mover",
    fields: [
      { name: "target_lat_deg", type: "number", units: "deg", required: true, min: -90, max: 90 },
      { name: "target_lon_deg", type: "number", units: "deg", required: true, min: -180, max: 180 },
      { name: "target_alt_m", type: "number", units: "m", required: true },
      { name: "speed_mps", type: "number", units: "m/s", required: false },
    ],
  },
  {
    verb: "follow_route",
    officer: "Mover",
    fields: [
      { name: "waypoints", type: "object", required: true, description: "JSON array of [lat, lon, alt] triples" },
      { name: "speed_mps", type: "number", units: "m/s", required: false },
      { name: "loop", type: "bool", required: false },
    ],
  },
  { verb: "halt", officer: "Mover", fields: [] },
  {
    verb: "assume_posture",
    officer: "Mover",
    fields: [
      {
        name: "posture",
        type: "enum",
        required: true,
        enumValues: ["HALTED", "MOUNTED", "DISMOUNTED", "DUG_IN", "ALERT", "REST"],
      },
      { name: "transition_s", type: "number", units: "s", required: false },
    ],
  },
  // ------- Communicator -------
  {
    verb: "send",
    officer: "Communicator",
    fields: [
      { name: "recipient_entity_id", type: "uuid", required: false },
      { name: "recipient_role", type: "string", required: false },
      {
        name: "channel",
        type: "enum",
        required: true,
        enumValues: ["VHF", "UHF", "HF", "SATCOM", "DATA"],
      },
      { name: "message_payload", type: "object", required: true, description: "JSON payload" },
      {
        name: "priority",
        type: "enum",
        required: false,
        enumValues: ["ROUTINE", "PRIORITY", "IMMEDIATE", "FLASH"],
      },
    ],
  },
  {
    verb: "relay",
    officer: "Communicator",
    fields: [
      { name: "source_entity_id", type: "uuid", required: true },
      { name: "recipient_entity_id", type: "uuid", required: true },
      {
        name: "channel",
        type: "enum",
        required: true,
        enumValues: ["VHF", "UHF", "HF", "SATCOM", "DATA"],
      },
    ],
  },
  {
    verb: "jam",
    officer: "Communicator",
    spatialArtifact: "jamming_circle",
    fields: [
      { name: "center_lat_deg", type: "number", units: "deg", required: true, min: -90, max: 90 },
      { name: "center_lon_deg", type: "number", units: "deg", required: true, min: -180, max: 180 },
      { name: "radius_m", type: "number", units: "m", required: true, min: 100, max: 8000 },
      { name: "power_w", type: "number", units: "W", required: true, min: 10, max: 1500 },
      {
        name: "band",
        type: "enum",
        required: true,
        enumValues: ["HF", "VHF", "UHF", "L", "S", "C", "X", "KU", "KA"],
      },
      { name: "duration_s", type: "number", units: "s", required: true },
    ],
  },
  {
    verb: "report",
    officer: "Communicator",
    fields: [
      {
        name: "report_type",
        type: "enum",
        required: true,
        enumValues: ["SITREP", "SPOTREP", "LOGSTAT", "CASEVAC", "INTREP"],
      },
      { name: "report_payload", type: "object", required: true, description: "JSON payload" },
      {
        name: "to_echelon",
        type: "enum",
        required: true,
        enumValues: ["COMPANY", "BATTALION", "BRIGADE", "DIVISION", "WHITE_CELL"],
      },
    ],
  },
  // ------- Commander -------
  {
    verb: "issue_order",
    officer: "Commander",
    fields: [
      { name: "to_entity_id", type: "uuid", required: false },
      {
        name: "to_echelon",
        type: "enum",
        required: false,
        enumValues: ["COMPANY", "BATTALION", "BRIGADE", "DIVISION", "WHITE_CELL"],
      },
      {
        name: "order_type",
        type: "enum",
        required: true,
        enumValues: ["MOVE", "ATTACK", "DEFEND", "RECON", "SUPPORT", "WITHDRAW"],
      },
      { name: "order_payload", type: "object", required: true, description: "JSON payload" },
      {
        name: "priority",
        type: "enum",
        required: false,
        enumValues: ["LOW", "MEDIUM", "HIGH"],
      },
    ],
  },
  {
    verb: "request_support",
    officer: "Commander",
    fields: [
      {
        name: "support_type",
        type: "enum",
        required: true,
        enumValues: ["FIRES", "ISR", "MEDEVAC", "LOGISTICS", "EW", "AIR"],
      },
      { name: "target_lat_deg", type: "number", units: "deg", required: false, min: -90, max: 90 },
      { name: "target_lon_deg", type: "number", units: "deg", required: false, min: -180, max: 180 },
      { name: "justification", type: "string", required: true },
      {
        name: "priority",
        type: "enum",
        required: true,
        enumValues: ["LOW", "MEDIUM", "HIGH", "IMMEDIATE"],
      },
    ],
  },
  {
    verb: "delegate",
    officer: "Commander",
    fields: [
      { name: "to_entity_id", type: "uuid", required: true },
      { name: "delegated_verbs", type: "object", required: true, description: "JSON array of verb names" },
      { name: "ttl_turns", type: "number", units: "turns", required: true, min: 1 },
    ],
  },
  {
    verb: "escalate",
    officer: "Commander",
    fields: [
      { name: "reason", type: "string", required: true },
      {
        name: "severity",
        type: "enum",
        required: true,
        enumValues: ["ROUTINE", "PRIORITY", "FLASH"],
      },
      {
        name: "to_echelon",
        type: "enum",
        required: true,
        enumValues: ["COMPANY", "BATTALION", "BRIGADE", "DIVISION", "WHITE_CELL"],
      },
      { name: "references", type: "object", required: false, description: "JSON object" },
    ],
  },
] as const;

export function verbsByOfficer(officer: OfficerType): readonly VerbSpec[] {
  return VERBS.filter((v) => v.officer === officer);
}

export function getVerb(name: string): VerbSpec | undefined {
  return VERBS.find((v) => v.verb === name);
}
