# Almighty — Capability profile schema (v1)

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

A **capability profile** is the immutable-from-scenario-start description
of what an entity can do in the simulation. Profiles drive three things:

1. **Agent decision-making** — CrewAI agents (WS-403, WS-404, WS-405)
   read profiles to know which verbs they can issue and within what bounds.
2. **Validator gating** — the CZML validator (WS-202) intersects the
   profile's `effect_parameter_ranges` with the CZML template's static
   constraints (WS-201) to gate every spatial artifact at commit time.
3. **Officer-tool capability checks** — the tool wrapper (WS-402) for
   each verb checks `action_verbs_available` before invoking the validator.

The profile is the single point where an entity's *what it can do* is
declared. Per-officer blocks (`sensor`, `effector`, `mover`,
`communicator`, `commander`) name the parameter paths that
[`officer-interfaces.md`](officer-interfaces.md) (WS-105) references — for
example, when WS-105 says "`range_m ≤ profile.sensor.<modality>.max_range_m`",
the path resolves to `<this profile>.sensor.<modality>.max_range_m`.

The companion JSON Schema is at
[`capability-profile.schema.json`](capability-profile.schema.json) (draft
2020-12). It is the structural contract; this doc is the semantic one.

---

## 1. Top-level fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `profile_id` | `uuid` | yes | Stable identifier. Edits that materially change profile semantics MUST fork to a new `profile_id` rather than bumping `version` once the profile is bound. |
| `version` | `int` | yes | Monotonic, ≥ 1. Pre-scenario edits bump version against the same `profile_id`. Frozen at first binding (see [§ 5](#5-versioning)). |
| `display_name` | `string` | yes | Human-readable for EXCON consoles and AAR. |
| `force_affiliation` | enum `BLUE \| RED \| WHITE \| NEUTRAL` | yes | Aligned with WS-101. RED profiles MAY include the `uncertainty` block; non-RED profiles MUST NOT. |
| `officer_types_available` | `[string]` | yes | Subset of `{SENSOR, EFFECTOR, MOVER, COMMUNICATOR, COMMANDER}`. Empty list is legal but rare (e.g., a beacon entity). |
| `action_verbs_available` | `[string]` | yes | Subset of the 20 verbs in WS-105. Each verb's officer type MUST appear in `officer_types_available` (validation rule, see [§ 4](#4-validation-rules)). |
| `sensor` | object | conditional | Required iff `SENSOR ∈ officer_types_available`. See [§ 2.1](#21-sensor-block). |
| `effector` | object | conditional | Required iff `EFFECTOR ∈ officer_types_available`. See [§ 2.2](#22-effector-block). |
| `mover` | object | conditional | Required iff `MOVER ∈ officer_types_available`. See [§ 2.3](#23-mover-block). |
| `communicator` | object | conditional | Required iff `COMMUNICATOR ∈ officer_types_available`. See [§ 2.4](#24-communicator-block). |
| `commander` | object | conditional | Required iff `COMMANDER ∈ officer_types_available`. See [§ 2.5](#25-commander-block). |
| `effect_parameter_ranges` | object | yes | Per-spatial-effect-family parameter bounds. See [§ 3](#3-effect-parameter-ranges). |
| `uncertainty` | object | optional | RED-only band declarations. See [§ 6](#6-uncertainty-bands-red-only). |
| `entity_bindings` | object | yes | Which entities pull this profile. See [§ 7](#7-entity-bindings). |
| `frozen_at` | `timestamptz` | optional | `null` while the profile is in draft. Set to a UTC timestamp at first binding. Once non-null, edits to `(profile_id, version)` are rejected. |
| `forked_from` | object | optional | `{ "profile_id": uuid, "version": int }` when this profile was forked from a previously frozen one. Provides AAR provenance. |

---

## 2. Per-officer blocks

### 2.1 `sensor` block

Drives the four Sensor verbs (`detect`, `track`, `classify`, `lose_track`).

```yaml
sensor:
  modalities:                 # per-modality config; missing modalities are unavailable
    EO_IR:        { max_range_m: 8000,  min_classify_dwell_s: 3.0 }
    RF:           { max_range_m: 80000, min_classify_dwell_s: 2.0 }
    RADAR:        { max_range_m: 50000, min_classify_dwell_s: 1.0 }
    ACOUSTIC:     { max_range_m: 4000,  min_classify_dwell_s: 5.0 }
    SEISMIC:      { max_range_m: 6000,  min_classify_dwell_s: 4.0 }
    MASINT_MULTI: { max_range_m: 30000, min_classify_dwell_s: 6.0 }
  max_concurrent_tracks: 24
  max_update_rate_hz: 5.0
  default_track_lifetime_s: 120
```

Modalities are the same set as WS-105's `sensor_modality` enum. A
modality not declared in `modalities` is implicitly unavailable — the
validator rejects `detect` calls with that modality.

### 2.2 `effector` block

Drives `engage`, `suppress`, `destroy`, `disable`.

```yaml
effector:
  weapon_systems:
    - id: notional.indirect.medium     # the string referenced in payload.weapon_system
      delivery_mode: INDIRECT          # DIRECT | INDIRECT | EW | CYBER
      effective_range_m: 25000
      ammo_remaining: 240
      time_of_flight_s: 32             # ballistic feasibility check
      supported_verbs: [engage, suppress, destroy]
    - id: notional.direct.smallarms
      delivery_mode: DIRECT
      effective_range_m: 600
      ammo_remaining: 6000
      time_of_flight_s: 0
      supported_verbs: [engage, suppress]
  max_suppression_area_m2: 1500000     # 1.5 km^2; over this -> adjudication
  cyber_disable: false                 # true unlocks disable.method=CYBER
```

`weapon_systems[*].id` is the exact string an agent passes in
`engage.weapon_system`. `supported_verbs` is the per-system gate — a
5.56 rifle profile lists `[engage, suppress]` only, so a `destroy` call
with that weapon fails at the validator. `delivery_mode = EW` weapon
systems borrow the Communicator-side jam capability (WS-105 § 2,
`disable` method `EW`).

### 2.3 `mover` block

Drives `move_to`, `follow_route`, `halt`, `assume_posture`.

```yaml
mover:
  cruise_speed_mps: 12.5
  max_speed_mps: 22.2
  allowed_postures: [HALTED, MOUNTED, DISMOUNTED, DUG_IN, ALERT, REST]
  posture_transitions:        # adjacency list; from -> [to, ...]
    HALTED:     [MOUNTED, REST, ALERT]
    MOUNTED:    [HALTED, ALERT]
    DISMOUNTED: [HALTED, DUG_IN, ALERT]
    DUG_IN:     [DISMOUNTED, ALERT]
    ALERT:      [HALTED, MOUNTED, DISMOUNTED, REST]
    REST:       [ALERT, HALTED]
```

`posture_transitions` resolves the open question carried over from
WS-105 § Open Questions. The transition matrix is per-profile because
different platforms have different doctrinal allowed transitions (e.g.,
a wheeled APC cannot `DUG_IN` directly without first becoming
`DISMOUNTED`).

### 2.4 `communicator` block

Drives `send`, `relay`, `jam`, `report`.

```yaml
communicator:
  channels: [VHF, UHF, HF, DATA]                     # available comms channels
  bands:                                             # per-band jam config
    VHF: { max_power_w: 200,  max_coverage_area_m2: 6000000 }
    UHF: { max_power_w: 200,  max_coverage_area_m2: 4000000 }
    L:   { max_power_w: 1000, max_coverage_area_m2: 2000000 }
  advertise_corridor: false                          # relay -> uas_corridor artifact
  reports_allowed: [SITREP, SPOTREP, LOGSTAT, INTREP]
```

Bands not present in `bands` are unavailable to `jam`. A profile with
`channels = []` cannot `send` at all; `relay` and `report` similarly
require a `channel` to be available.

### 2.5 `commander` block

Drives `issue_order`, `request_support`, `delegate`, `escalate`.

```yaml
commander:
  echelon: BATTALION                                  # COMPANY | BATTALION | BRIGADE | DIVISION | WHITE_CELL
  subordinates_under: [notional.ground.bct.company]   # type_subtype_refs (entity-binding match)
  delegatable_verbs: [move_to, engage, suppress, jam] # subset of own action_verbs_available
  request_support_types: [FIRES, ISR, MEDEVAC, LOGISTICS, EW, AIR]
  max_delegation_ttl_turns: 6
```

`subordinates_under` resolves a Commander entity's chain of command at
binding time: an `issue_order` call's recipient must be an entity whose
`type_subtype_ref` matches one of these patterns OR be an
`entity_bindings.specific_ids` member.

---

## 3. Effect parameter ranges

`effect_parameter_ranges` is keyed by spatial-effect-family name (per
[`docs/glossary.md` § 2](../glossary.md#2-effect-families)). It is the
profile-side input the validator (WS-202) intersects with the
template-side static range from WS-201.

```yaml
effect_parameter_ranges:
  ew_cone:
    azimuth_deg:        { min: 0,    max: 359 }
    beamwidth_deg:      { min: 5,    max: 60 }
    effective_range_m:  { min: 1000, max: 50000 }
  jamming_circle:
    radius_m:           { min: 100,  max: 8000 }
    power_w:            { min: 10,   max: 1000 }
  indirect_fire_arc:
    range_m:            { min: 1000, max: 30000 }
    dispersion_ellipse_a_m: { min: 5, max: 250 }
    dispersion_ellipse_b_m: { min: 5, max: 250 }
    time_of_flight_s:   { min: 1,    max: 90 }
  radar_fan:
    sweep_arc_deg:      { min: 5,    max: 360 }
    range_m:            { min: 500,  max: 80000 }
  ir_plume:
    peak_intensity_w_per_sr: { min: 1, max: 5000 }
    decay_s:            { min: 5,    max: 300 }
  masint_cell:
    polygon_area_m2:    { min: 1000, max: 10000000 }
    dwell_s:            { min: 30,   max: 7200 }
  keyhole_footprint:
    polygon_area_m2:    { min: 100,  max: 200000 }
  uas_corridor:
    altitude_band_lower_m: { min: 100, max: 10000 }
    altitude_band_upper_m: { min: 100, max: 12000 }
  satellite_swath:
    swath_width_m:      { min: 5000,  max: 250000 }
    pass_duration_s:    { min: 30,    max: 1800 }
```

A family that is wholly inapplicable to a profile (e.g., a foot-mobile
infantry profile with no satellite assets) MAY OMIT that family's entry.
The validator interprets a missing entry as "this profile cannot emit
this family at all" and rejects any CZML packet that references it.

---

## 4. Validation rules

The JSON Schema enforces shape; these semantic rules are enforced by the
validator (WS-202) at scenario-start profile registration:

1. **Officer ↔ verb consistency.** Every verb in `action_verbs_available`
   must belong to an officer type in `officer_types_available`. Verb-to-
   officer mapping is the one in WS-105 § Summary.
2. **Per-officer block presence.** If `X ∈ officer_types_available`, the
   `<x>` block (lowercased) must be present and non-empty. Conversely, a
   block for an officer not in `officer_types_available` must be absent.
3. **Verb-specific field requirements.** Particular verbs imply
   particular per-officer-block fields:
   - `engage / suppress / destroy / disable` ⇒ `effector.weapon_systems` non-empty.
   - `detect / track / classify` ⇒ `sensor.modalities` non-empty.
   - `jam` ⇒ `communicator.bands` non-empty.
   - `assume_posture` ⇒ `mover.posture_transitions` covers all postures
     in `mover.allowed_postures`.
   - `delegate` ⇒ `commander.delegatable_verbs ⊆ action_verbs_available`.
4. **Effect-family / verb consistency.** A profile that emits a spatial
   family (per WS-105 § Summary) must include that family in
   `effect_parameter_ranges`. The validator looks up the verb's
   typically-emitted family from a fixed table and rejects at registration
   time if missing.
5. **Uncertainty on RED only.** If `uncertainty` is present,
   `force_affiliation` MUST be `RED`. A WHITE/BLUE/NEUTRAL profile with
   an `uncertainty` block is rejected.

---

## 5. Versioning

Profiles are mutable in draft and frozen at first binding.

- **Draft state:** `frozen_at = null`. Pre-scenario edits push a new
  `version` against the same `profile_id`. White cell authors profiles
  in this state through the white cell console (WS-505).
- **Frozen state:** `frozen_at = <utc>`. This is set automatically the
  first time an entity in any scenario binds to `(profile_id, version)`.
  Any subsequent edit to the *same* `(profile_id, version)` is rejected;
  the only path forward is a new `version` (if no scenario has bound to
  the current version) or a fork (new `profile_id`, with `forked_from`
  set).
- **Forking:** a fork copies the current profile, assigns a new
  `profile_id`, sets `version = 1`, and records `forked_from =
  {profile_id, version}`. AAR (WS-506) renders the lineage when a
  scenario's profile graph is traversed.

The runbook's "immutable from turn 1" rule is therefore a consequence of
"immutable from first binding"; turn 1 is just the most common first
binding event, not a special-cased trigger.

---

## 6. Uncertainty bands (RED only)

Red-side capabilities reflect what the *opponent* believes about the
adversary, not ground truth. The optional `uncertainty` block declares
bands on selected fields:

```yaml
uncertainty:
  effector.weapon_systems[notional.indirect.medium].effective_range_m:
    band_pct: 0.20      # ±20% relative
  sensor.modalities.RADAR.max_range_m:
    band_pct: 0.30
  communicator.bands.UHF.max_power_w:
    band_lower: 50      # absolute lower
    band_upper: 800     # absolute upper
```

Resolution rules:

- **Agent reasoning.** Red agents (WS-404) reason over the uncertainty
  band — e.g., a red S3 issuing an `engage` order computes range
  feasibility against the *upper bound* of the band when it wants the
  shot to succeed and against the *lower bound* when it wants to claim
  it cannot reach.
- **Validator clamping.** When red emits a CZML packet, the validator
  clamps the parameter to the upper bound of the band before the
  effect-family range check. This means red can claim ±20% on its
  effector range but cannot actually exceed the upper bound on the wire.
- **AAR transparency.** The white cell sees the unbounded ground-truth
  value as authored; the band is what the *blue* side, were they
  observing, would infer.
- **Uncertainty paths.** The keys in `uncertainty` are JSON-Pointer-style
  paths into the profile object. Path syntax: dot-separated for objects,
  square-brackets for array elements addressed by `id` (where applicable)
  or by index. The JSON Schema validates the path syntax; semantic
  resolution is the validator's job.

---

## 7. Entity bindings

`entity_bindings` declares which entities use this profile.

```yaml
entity_bindings:
  type_subtype_refs:
    - notional.ground.bct.battalion
    - notional.ground.bct.hq.command-vehicle
  specific_ids:
    - 1c3b8f6e-2c7e-4a8c-9b3d-7a1d2f5e9a01     # one specific entity
```

Resolution at scenario start:

- An entity's `capability_set_ref` (per WS-101) must match exactly one
  profile's binding. If `entity_id` is in any profile's `specific_ids`,
  that profile wins. Otherwise, the entity's `type_subtype_ref` is
  matched against `type_subtype_refs` of every profile; exactly one must
  match.
- Multiple matches at scenario start is a registration error and blocks
  scenario start.
- An entity that matches no profile gets the `null_profile`
  (officer_types_available = [], action_verbs_available = []) and is
  read-only on the wire (publishes Entity State only).

---

## 8. Worked examples

Two complete profiles follow. Both validate against
[`capability-profile.schema.json`](capability-profile.schema.json).

### 8.1 Notional US BCT (blue) — `us-bct@1`

A US Brigade Combat Team battalion-level profile. Fully populated; no
`uncertainty` (BLUE forces don't have it).

```json
{
  "profile_id": "00000000-bbbb-0001-0000-000000000001",
  "version": 1,
  "display_name": "Notional US BCT — battalion",
  "force_affiliation": "BLUE",
  "officer_types_available": ["SENSOR", "EFFECTOR", "MOVER", "COMMUNICATOR", "COMMANDER"],
  "action_verbs_available": [
    "detect", "track", "classify", "lose_track",
    "engage", "suppress", "destroy", "disable",
    "move_to", "follow_route", "halt", "assume_posture",
    "send", "relay", "report",
    "issue_order", "request_support", "delegate", "escalate"
  ],
  "sensor": {
    "modalities": {
      "EO_IR":        { "max_range_m": 8000,  "min_classify_dwell_s": 3.0 },
      "RADAR":        { "max_range_m": 50000, "min_classify_dwell_s": 1.0 },
      "RF":           { "max_range_m": 60000, "min_classify_dwell_s": 2.0 },
      "MASINT_MULTI": { "max_range_m": 25000, "min_classify_dwell_s": 6.0 }
    },
    "max_concurrent_tracks": 32,
    "max_update_rate_hz": 5.0,
    "default_track_lifetime_s": 180
  },
  "effector": {
    "weapon_systems": [
      {
        "id": "notional.indirect.medium",
        "delivery_mode": "INDIRECT",
        "effective_range_m": 25000,
        "ammo_remaining": 240,
        "time_of_flight_s": 32,
        "supported_verbs": ["engage", "suppress", "destroy"]
      },
      {
        "id": "notional.direct.smallarms",
        "delivery_mode": "DIRECT",
        "effective_range_m": 600,
        "ammo_remaining": 12000,
        "time_of_flight_s": 0,
        "supported_verbs": ["engage", "suppress"]
      }
    ],
    "max_suppression_area_m2": 1500000,
    "cyber_disable": false
  },
  "mover": {
    "cruise_speed_mps": 12.5,
    "max_speed_mps": 22.2,
    "allowed_postures": ["HALTED", "MOUNTED", "DISMOUNTED", "DUG_IN", "ALERT", "REST"],
    "posture_transitions": {
      "HALTED":     ["MOUNTED", "REST", "ALERT"],
      "MOUNTED":    ["HALTED", "ALERT"],
      "DISMOUNTED": ["HALTED", "DUG_IN", "ALERT"],
      "DUG_IN":     ["DISMOUNTED", "ALERT"],
      "ALERT":      ["HALTED", "MOUNTED", "DISMOUNTED", "REST"],
      "REST":       ["ALERT", "HALTED"]
    }
  },
  "communicator": {
    "channels": ["VHF", "UHF", "HF", "SATCOM", "DATA"],
    "bands": {
      "VHF": { "max_power_w": 100,  "max_coverage_area_m2": 4000000 },
      "UHF": { "max_power_w": 100,  "max_coverage_area_m2": 3000000 }
    },
    "advertise_corridor": false,
    "reports_allowed": ["SITREP", "SPOTREP", "LOGSTAT", "INTREP", "CASEVAC"]
  },
  "commander": {
    "echelon": "BATTALION",
    "subordinates_under": ["notional.ground.bct.company"],
    "delegatable_verbs": ["move_to", "follow_route", "engage", "suppress"],
    "request_support_types": ["FIRES", "ISR", "MEDEVAC", "LOGISTICS", "AIR"],
    "max_delegation_ttl_turns": 6
  },
  "effect_parameter_ranges": {
    "indirect_fire_arc": {
      "range_m":          { "min": 1000, "max": 25000 },
      "dispersion_ellipse_a_m": { "min": 5, "max": 200 },
      "dispersion_ellipse_b_m": { "min": 5, "max": 200 },
      "time_of_flight_s": { "min": 1,    "max": 60 }
    },
    "radar_fan": {
      "sweep_arc_deg":    { "min": 10, "max": 360 },
      "range_m":          { "min": 500,  "max": 50000 }
    },
    "ir_plume": {
      "peak_intensity_w_per_sr": { "min": 1, "max": 4000 },
      "decay_s":          { "min": 5,    "max": 240 }
    },
    "masint_cell": {
      "polygon_area_m2":  { "min": 1000, "max": 4000000 },
      "dwell_s":          { "min": 30,   "max": 3600 }
    },
    "keyhole_footprint": {
      "polygon_area_m2":  { "min": 100,  "max": 100000 }
    }
  },
  "entity_bindings": {
    "type_subtype_refs": [
      "notional.ground.bct.battalion",
      "notional.ground.bct.hq.command-vehicle",
      "notional.ground.bct.company"
    ]
  }
}
```

### 8.2 Notional peer adversary (red) — `peer@1`

A peer-level OpFor battalion. Includes `uncertainty` bands on what the
blue side cannot precisely know about the adversary's reach.

```json
{
  "profile_id": "00000000-rrrr-0001-0000-000000000001",
  "version": 1,
  "display_name": "Notional peer adversary — battalion",
  "force_affiliation": "RED",
  "officer_types_available": ["SENSOR", "EFFECTOR", "MOVER", "COMMUNICATOR", "COMMANDER"],
  "action_verbs_available": [
    "detect", "track", "classify", "lose_track",
    "engage", "suppress", "destroy", "disable",
    "move_to", "follow_route", "halt", "assume_posture",
    "send", "relay", "jam", "report",
    "issue_order", "request_support", "delegate", "escalate"
  ],
  "sensor": {
    "modalities": {
      "EO_IR":        { "max_range_m": 6000,  "min_classify_dwell_s": 4.0 },
      "RADAR":        { "max_range_m": 60000, "min_classify_dwell_s": 1.5 },
      "RF":           { "max_range_m": 90000, "min_classify_dwell_s": 2.0 }
    },
    "max_concurrent_tracks": 24,
    "max_update_rate_hz": 4.0,
    "default_track_lifetime_s": 150
  },
  "effector": {
    "weapon_systems": [
      {
        "id": "notional.indirect.medium",
        "delivery_mode": "INDIRECT",
        "effective_range_m": 30000,
        "ammo_remaining": 360,
        "time_of_flight_s": 35,
        "supported_verbs": ["engage", "suppress", "destroy"]
      },
      {
        "id": "notional.ew.tactical",
        "delivery_mode": "EW",
        "effective_range_m": 50000,
        "ammo_remaining": 99999,
        "time_of_flight_s": 0,
        "supported_verbs": ["disable"]
      }
    ],
    "max_suppression_area_m2": 2500000,
    "cyber_disable": false
  },
  "mover": {
    "cruise_speed_mps": 13.9,
    "max_speed_mps": 25.0,
    "allowed_postures": ["HALTED", "MOUNTED", "DISMOUNTED", "DUG_IN", "ALERT"],
    "posture_transitions": {
      "HALTED":     ["MOUNTED", "ALERT"],
      "MOUNTED":    ["HALTED", "ALERT"],
      "DISMOUNTED": ["HALTED", "DUG_IN", "ALERT"],
      "DUG_IN":     ["DISMOUNTED", "ALERT"],
      "ALERT":      ["HALTED", "MOUNTED", "DISMOUNTED"]
    }
  },
  "communicator": {
    "channels": ["VHF", "UHF", "HF", "DATA"],
    "bands": {
      "VHF": { "max_power_w": 250, "max_coverage_area_m2": 8000000 },
      "UHF": { "max_power_w": 250, "max_coverage_area_m2": 6000000 },
      "L":   { "max_power_w": 1500, "max_coverage_area_m2": 4000000 }
    },
    "advertise_corridor": true,
    "reports_allowed": ["SITREP", "SPOTREP", "INTREP"]
  },
  "commander": {
    "echelon": "BATTALION",
    "subordinates_under": ["notional.peer.company"],
    "delegatable_verbs": ["move_to", "follow_route", "engage", "suppress", "jam"],
    "request_support_types": ["FIRES", "ISR", "EW", "AIR"],
    "max_delegation_ttl_turns": 4
  },
  "effect_parameter_ranges": {
    "indirect_fire_arc": {
      "range_m":          { "min": 1000, "max": 30000 },
      "dispersion_ellipse_a_m": { "min": 8, "max": 300 },
      "dispersion_ellipse_b_m": { "min": 8, "max": 300 },
      "time_of_flight_s": { "min": 1,    "max": 90 }
    },
    "radar_fan": {
      "sweep_arc_deg":    { "min": 5,   "max": 360 },
      "range_m":          { "min": 500, "max": 60000 }
    },
    "jamming_circle": {
      "radius_m":         { "min": 200, "max": 8000 },
      "power_w":          { "min": 50,  "max": 1500 }
    },
    "ew_cone": {
      "azimuth_deg":      { "min": 0,    "max": 359 },
      "beamwidth_deg":    { "min": 5,    "max": 60 },
      "effective_range_m": { "min": 1000, "max": 50000 }
    },
    "ir_plume": {
      "peak_intensity_w_per_sr": { "min": 1, "max": 5000 },
      "decay_s":          { "min": 5,    "max": 300 }
    },
    "uas_corridor": {
      "altitude_band_lower_m": { "min": 100, "max": 6000 },
      "altitude_band_upper_m": { "min": 100, "max": 8000 }
    }
  },
  "uncertainty": {
    "effector.weapon_systems[notional.indirect.medium].effective_range_m": { "band_pct": 0.20 },
    "effector.weapon_systems[notional.ew.tactical].effective_range_m": { "band_pct": 0.30 },
    "sensor.modalities.RADAR.max_range_m": { "band_pct": 0.25 },
    "communicator.bands.L.max_power_w": { "band_lower": 500, "band_upper": 2000 }
  },
  "entity_bindings": {
    "type_subtype_refs": [
      "notional.peer.battalion",
      "notional.peer.hq.command-vehicle",
      "notional.peer.company"
    ]
  }
}
```

---

## 9. Open questions

1. **Capability inheritance.** Two BCT companies under the same battalion
   share most capabilities. v1 requires a separate profile per
   `type_subtype_ref` if the capabilities differ at all; there's no
   inheritance. Tracked for v2.
2. **Live editing during scenario.** A frozen profile cannot be edited.
   But the white cell may need to revoke a verb mid-scenario (e.g.,
   "blue can no longer call `destroy`"). v1 handles this through the
   override gateway (WS-303), not profile mutation. Confirm with the
   white cell console design (WS-505).
3. **Ammo persistence across turns.** `ammo_remaining` is a profile
   field, but the *value* changes as the scenario progresses. v1 stores
   the per-entity remaining ammo on the entity row (out-of-schema for
   profile) and treats the profile field as the *initial* allocation.
   This needs explicit wording before WS-202 implements.
4. **Posture transition costs.** v1 has a flat adjacency list; doctrine
   often has time/fuel costs per transition. Out of scope.
5. **`null_profile` semantics for non-combatants.** A civilian vehicle
   in the scenario binds to `null_profile`; should it still be visible
   on EXCON consoles? Likely yes for white cell, no for blue/red. Decide
   in WS-504 / WS-505.
6. **Uncertainty path syntax.** Current syntax (dot + array-by-id)
   handles every WS-105 reference but is informal. If more complex
   structures appear in v2, adopting RFC 6901 JSON Pointer is the natural
   upgrade.

---

## References

- Officer interface contracts: [`officer-interfaces.md`](officer-interfaces.md) (WS-105)
- Glossary — officer types, effect families, force affiliations: [`docs/glossary.md`](../glossary.md)
- Neutral schema: [`docs/schema/entity-event.md`](entity-event.md) (WS-101)
- Capability profile library (downstream): WS-107 (#11)
- CZML validator (downstream): WS-202 (#14)
- Officer interface tools (downstream): WS-402 (#22)
- Effect artifact taxonomy (downstream): WS-108 (#12)
- White cell console (downstream): WS-505 (#30)
