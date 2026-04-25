# Almighty — Neutral entity/event schema (v1)

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

This document specifies the neutral data model that the DIS adapter
(WS-102) and HLA adapter (WS-103) both project from. It is the
authoritative shape used by the PyRapide kernel (WS-104), the officer
interface tools (WS-402), and the live CZML adapter (WS-503).

Two top-level entities are defined: **entities** and **events**.

---

## Conventions

- All timestamps are UTC, ISO-8601, with microsecond precision (`timestamptz`).
- All identifiers are RFC 4122 UUID v4 unless otherwise noted.
- Coordinates use WGS-84 for geodetic (lat/lon/alt) and earth-centered
  earth-fixed (ECEF) for engineering. Both are stored — the kernel never
  recomputes one from the other on the read path.
- Velocity is stored in ECEF coordinates (m/s). Orientation is stored as a
  unit quaternion `(w, x, y, z)`.
- Physical units are SI throughout: meters, m/s, radians (where applicable).
- The namespace boundary is `(tenant_id, scenario_id)` — every record
  carries both, and every query is parameterized on both. See
  [`docs/glossary.md#tenant-isolation`](../glossary.md#tenant-isolation).

---

## 1. Entity schema

An **entity** is anything that occupies state in the simulated battlespace:
platforms, ground units, air units, maritime units, satellites, jammers,
non-kinetic emitters. Adjudication artifacts (sensor observations, effects)
are NOT entities — they are events with bound artifacts (see WS-108).

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `entity_id` | `uuid` | yes | Primary key. |
| `tenant_id` | `uuid` | yes | Namespace boundary. |
| `scenario_id` | `uuid` | yes | Namespace boundary. |
| `type_category` | `enum entity_type_category` | yes | Top-level taxonomy. See enum values below. |
| `type_subtype_ref` | `text` | yes | Free-form taxonomy reference (e.g., `notional.ground.bct.battalion`). Resolves against the type taxonomy registry (out of scope for v1; treat as opaque label). |
| `display_name` | `text` | yes | Human-readable label for EXCON consoles and AAR. |
| `force_affiliation` | `enum force_affiliation` | yes | One of `BLUE`, `RED`, `WHITE`, `NEUTRAL`. |
| `position_lat_deg` | `double precision` | yes | WGS-84 geodetic latitude, decimal degrees, range `[-90, 90]`. |
| `position_lon_deg` | `double precision` | yes | WGS-84 geodetic longitude, decimal degrees, range `[-180, 180]`. |
| `position_alt_m` | `double precision` | yes | Height above WGS-84 ellipsoid in meters. |
| `position_ecef_x_m` | `double precision` | yes | ECEF X in meters. |
| `position_ecef_y_m` | `double precision` | yes | ECEF Y in meters. |
| `position_ecef_z_m` | `double precision` | yes | ECEF Z in meters. |
| `velocity_ecef_vx_mps` | `double precision` | yes | ECEF velocity X in m/s. |
| `velocity_ecef_vy_mps` | `double precision` | yes | ECEF velocity Y in m/s. |
| `velocity_ecef_vz_mps` | `double precision` | yes | ECEF velocity Z in m/s. |
| `orientation_qw` | `double precision` | yes | Quaternion w component. |
| `orientation_qx` | `double precision` | yes | Quaternion x component. |
| `orientation_qy` | `double precision` | yes | Quaternion y component. |
| `orientation_qz` | `double precision` | yes | Quaternion z component. |
| `capability_set_ref` | `text` | yes | FK to a capability profile `(profile_id, version)` per WS-106. Stored as `"<profile_id>@<version>"` until WS-106 lands. |
| `created_at` | `timestamptz` | yes | Default `now()`. |
| `updated_at` | `timestamptz` | yes | Default `now()`; updated on row update. |

### Type category enum

`entity_type_category` is one of:

- `PLATFORM` — vehicles, aircraft, ships, satellites that carry officers.
- `GROUND_UNIT` — dismounted formations and emplaced positions.
- `AIR_UNIT` — manned aircraft and crewed UAS.
- `MARITIME_UNIT` — surface vessels and submarines.
- `SPACE_UNIT` — satellites and orbital assets.
- `NON_KINETIC` — emitters, decoys, and synthetic entities (jammers,
  spoofers, EW arrays).
- `OTHER` — escape hatch; should be rare and reviewed.

### Constraints

1. `entity_id` is unique globally (UUID v4 collision is the bound).
2. `(tenant_id, scenario_id, entity_id)` is the natural lookup key.
3. Geodetic and ECEF positions must agree within 1 m. v1 trusts the
   producer; the kernel does NOT recompute on write.
4. Quaternion components must satisfy `qw² + qx² + qy² + qz² ≈ 1` (unit
   quaternion). Tolerance: ±1e-6.
5. `capability_set_ref` must resolve against a known capability profile at
   scenario start. Validation deferred to WS-106 + WS-202.

---

## 2. Event schema

An **event** is the atomic unit of simulation history. Every state change
is an event. Events are immutable once committed to the DAG.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `event_id` | `uuid` | yes | Primary key. |
| `tenant_id` | `uuid` | yes | Namespace boundary. |
| `scenario_id` | `uuid` | yes | Namespace boundary. |
| `turn` | `int` | yes | 0-indexed turn within the scenario. |
| `source_officer_type` | `enum officer_type` | yes | One of `SENSOR`, `EFFECTOR`, `MOVER`, `COMMUNICATOR`, `COMMANDER`. |
| `source_entity_id` | `uuid` | yes | FK to `entities.entity_id`. |
| `action_verb` | `text` | yes | One of the 20 verbs per WS-105. Constraint deferred to WS-105 (see "Open constraints" below). |
| `payload` | `jsonb` | yes | Verb-specific parameters. Schema per verb defined in WS-105. May be `'{}'`. |
| `causal_predecessors` | `uuid[]` | yes | Array of preceding event IDs in the same scenario. Empty for root events. |
| `ts` | `timestamptz` | yes | Sim-clock or wall-clock per scenario config (default wall-clock). |
| `created_at` | `timestamptz` | yes | Default `now()`. |

### Officer type enum

`officer_type` is one of:

- `SENSOR`
- `EFFECTOR`
- `MOVER`
- `COMMUNICATOR`
- `COMMANDER`

See [`docs/glossary.md#1-officer-types`](../glossary.md#1-officer-types) for
verb assignments per type.

### Constraints

1. `event_id` is unique globally.
2. `(tenant_id, scenario_id)` is the namespace boundary; `causal_predecessors`
   MUST reference events in the same scenario (this rules out cross-scenario
   leakage even within the same tenant). Enforcement options:
   - **Application-level:** kernel write path checks each predecessor's
     `(tenant_id, scenario_id)` matches the new event before insert. This
     is the v1 enforcement point.
   - **Database-level (deferred):** a trigger on `INSERT` validates the
     array. Tracked under WS-104 once the DAG namespacing lands.
3. `source_entity_id` MUST reference an entity in the same
   `(tenant_id, scenario_id)`. Enforcement: foreign-key constraint at the
   DB level. Defined in `events.sql` as a composite FK.
4. `turn` is monotonic non-decreasing within a scenario, but not strictly
   increasing — multiple events per turn are normal.
5. `action_verb` text values are constrained to the 20 verbs defined in
   WS-105 (#9). Enforcement deferred there.

### Open constraints (deferred to downstream issues)

- WS-104 (#8): predecessor cross-scenario validation as a DB trigger.
- WS-105 (#9): `CHECK (action_verb IN (...))` once the canonical 20-verb
  list is locked.
- WS-106 (#10): `capability_set_ref` validation against the profile registry.
- WS-301 (#17): RLS policies parameterized on `(tenant_id, scenario_id)`.

---

## 3. Indexes

The two namespace-bound tables share an indexing pattern:

- `entities`:
  - PK on `entity_id`.
  - Composite index on `(tenant_id, scenario_id)` for the namespace scan.
  - Composite index on `(tenant_id, scenario_id, force_affiliation)` for
    EXCON sidebar listings (WS-504) which always filter by friendly side.
- `events`:
  - PK on `event_id`.
  - Composite index on `(tenant_id, scenario_id, turn)` for the AAR replay
    timeline scan (WS-506).
  - GIN index on `causal_predecessors` for ancestor lookup (PyRapide DAG
    queries — WS-104).
  - Composite index on `(tenant_id, scenario_id, source_entity_id)` for
    "all events this entity emitted" lookups (used by the override
    gateway, WS-303).

---

## 4. Examples

### Two entity rows

**Blue battalion HQ command vehicle**, Cumberland River west bank:

```json
{
  "entity_id": "1c3b8f6e-2c7e-4a8c-9b3d-7a1d2f5e9a01",
  "tenant_id": "11111111-1111-1111-1111-111111111111",
  "scenario_id": "22222222-2222-2222-2222-222222222222",
  "type_category": "PLATFORM",
  "type_subtype_ref": "notional.ground.bct.hq.command-vehicle",
  "display_name": "BLUE-HQ-1",
  "force_affiliation": "BLUE",
  "position_lat_deg": 36.1750,
  "position_lon_deg": -86.7850,
  "position_alt_m": 165.0,
  "position_ecef_x_m": 304113.21,
  "position_ecef_y_m": -5142308.55,
  "position_ecef_z_m": 3744298.10,
  "velocity_ecef_vx_mps": 0.0,
  "velocity_ecef_vy_mps": 0.0,
  "velocity_ecef_vz_mps": 0.0,
  "orientation_qw": 1.0,
  "orientation_qx": 0.0,
  "orientation_qy": 0.0,
  "orientation_qz": 0.0,
  "capability_set_ref": "us-bct@1",
  "created_at": "2026-04-25T15:30:00.000000Z",
  "updated_at": "2026-04-25T15:30:00.000000Z"
}
```

**Red UAS ISR platform**, east of the river:

```json
{
  "entity_id": "1c3b8f6e-2c7e-4a8c-9b3d-7a1d2f5e9a02",
  "tenant_id": "11111111-1111-1111-1111-111111111111",
  "scenario_id": "22222222-2222-2222-2222-222222222222",
  "type_category": "AIR_UNIT",
  "type_subtype_ref": "notional.air.uas.medium",
  "display_name": "RED-UAS-1",
  "force_affiliation": "RED",
  "position_lat_deg": 36.1810,
  "position_lon_deg": -86.7720,
  "position_alt_m": 1500.0,
  "position_ecef_x_m": 305021.40,
  "position_ecef_y_m": -5141001.13,
  "position_ecef_z_m": 3745118.96,
  "velocity_ecef_vx_mps": -32.5,
  "velocity_ecef_vy_mps": 12.1,
  "velocity_ecef_vz_mps": 0.0,
  "orientation_qw": 0.7071,
  "orientation_qx": 0.0,
  "orientation_qy": 0.0,
  "orientation_qz": 0.7071,
  "capability_set_ref": "peer@1",
  "created_at": "2026-04-25T15:30:00.000000Z",
  "updated_at": "2026-04-25T15:30:00.000000Z"
}
```

### Three event rows

**Root event — red commander issues an ISR order:**

```json
{
  "event_id": "aaaaaaaa-0001-0000-0000-000000000001",
  "tenant_id": "11111111-1111-1111-1111-111111111111",
  "scenario_id": "22222222-2222-2222-2222-222222222222",
  "turn": 1,
  "source_officer_type": "COMMANDER",
  "source_entity_id": "1c3b8f6e-2c7e-4a8c-9b3d-7a1d2f5e9a02",
  "action_verb": "issue_order",
  "payload": {
    "order_type": "isr.collect",
    "target_area": "west_bank.crossing_zone",
    "priority": "high"
  },
  "causal_predecessors": [],
  "ts": "2026-04-25T15:31:00.000000Z",
  "created_at": "2026-04-25T15:31:00.000000Z"
}
```

**Caused event — UAS sensor detects blue HQ vehicle:**

```json
{
  "event_id": "aaaaaaaa-0001-0000-0000-000000000002",
  "tenant_id": "11111111-1111-1111-1111-111111111111",
  "scenario_id": "22222222-2222-2222-2222-222222222222",
  "turn": 1,
  "source_officer_type": "SENSOR",
  "source_entity_id": "1c3b8f6e-2c7e-4a8c-9b3d-7a1d2f5e9a02",
  "action_verb": "detect",
  "payload": {
    "detected_entity_id": "1c3b8f6e-2c7e-4a8c-9b3d-7a1d2f5e9a01",
    "detection_method": "EO/IR",
    "confidence": 0.78,
    "czml_template": "uas-corridor"
  },
  "causal_predecessors": ["aaaaaaaa-0001-0000-0000-000000000001"],
  "ts": "2026-04-25T15:32:30.000000Z",
  "created_at": "2026-04-25T15:32:30.000000Z"
}
```

**Caused event — blue commander escalates after detection report:**

```json
{
  "event_id": "aaaaaaaa-0001-0000-0000-000000000003",
  "tenant_id": "11111111-1111-1111-1111-111111111111",
  "scenario_id": "22222222-2222-2222-2222-222222222222",
  "turn": 1,
  "source_officer_type": "COMMANDER",
  "source_entity_id": "1c3b8f6e-2c7e-4a8c-9b3d-7a1d2f5e9a01",
  "action_verb": "escalate",
  "payload": {
    "reason": "ISR overwatch detected; expecting follow-on effects",
    "to_echelon": "brigade"
  },
  "causal_predecessors": ["aaaaaaaa-0001-0000-0000-000000000002"],
  "ts": "2026-04-25T15:33:15.000000Z",
  "created_at": "2026-04-25T15:33:15.000000Z"
}
```

The three events form a chain: red ISR order → UAS detection → blue
escalation. The PyRapide DAG (WS-104) preserves this causality on replay
(WS-506) and lets the override gateway (WS-303) trace any commit back to
its triggering officer action.

---

## 5. Adapter projections

This schema is the source of truth. Adapter contracts in WS-102 and WS-103
spell out the per-field mapping into wire-level shapes:

- **DIS PDU adapter** (WS-102): projects entities to Entity State PDUs and
  events (per verb) to Fire / Detonation / Signal / Transmitter / Receiver
  PDUs.
- **HLA FOM adapter** (WS-103): projects entities to RPR-FOM
  `BaseEntity.PhysicalEntity` classes; events to corresponding
  interactions.

Both adapters MUST be lossless on the round trip from neutral schema →
wire shape → neutral schema for the v1 in-scope subset. Lossy mappings
are flagged in the adapter docs.

---

## References

- DDL stubs: [`kernel/schema/entities.sql`](../../kernel/schema/entities.sql), [`kernel/schema/events.sql`](../../kernel/schema/events.sql).
- Architecture: [`docs/architecture.md`](../architecture.md), [`docs/diagrams/architecture-v1.svg`](../diagrams/architecture-v1.svg).
- Glossary — officer types, force affiliations: [`docs/glossary.md`](../glossary.md).
- DIS adapter contract (downstream): WS-102 (#6).
- HLA adapter contract (downstream): WS-103 (#7).
- DAG namespacing (downstream): WS-104 (#8).
- Officer interface verbs (downstream): WS-105 (#9).
- Capability profile schema (downstream): WS-106 (#10).
- Effect artifact taxonomy (downstream): WS-108 (#12).
