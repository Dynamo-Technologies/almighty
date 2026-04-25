# Almighty — DIS PDU adapter contract (v1)

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

This document specifies the translation contract from the neutral entity /
event schema in [`entity-event.md`](entity-event.md) (WS-101) to IEEE
1278.1 Distributed Interactive Simulation (DIS) Protocol Data Units. It
defines field-level mappings, scope of in-scope PDU families, and lossy
mappings that callers must accept.

**No implementation is in scope here.** This is a contract authored ahead of
the adapter service so downstream consumers (kernel write path, federate
gateways) can plan against a stable shape.

References to IEEE 1278.1 cite section numbers from the IEEE Std 1278.1-2012
revision; the spec text itself is not reproduced. Public summaries are
linked in [§ References](#references).

---

## 1. Scope

### 1.1 PDU families in scope for v1

| PDU family | Family code | IEEE 1278.1 § | Justification |
|---|---|---|---|
| Entity State | 1 | § 5.3.3 | Required for every entity in the WS-101 schema. The kernel commits one Entity State PDU per entity per heartbeat. |
| Fire | 2 | § 5.4.3 | Effector verbs (`engage`, `suppress`, `destroy`, `disable`) emit Fire PDUs at the moment the munition leaves the firer. |
| Detonation | 3 | § 5.4.4 | Required follow-on for any Fire PDU once the round resolves at the impact point. Carries effect outcome. |
| Signal | 26 | § 5.8.4 | Communicator verbs (`send`, `relay`, `report`) project to Signal PDUs carrying application-level message payloads. |
| Transmitter | 25 | § 5.8.3 | `Communicator.jam` and active-emission Sensor verbs produce Transmitter PDUs describing the emitting station. |
| Receiver | 27 | § 5.8.5 | `Sensor.detect` / `track` / `classify` verbs project to Receiver PDUs describing the receiving station and detected emission characteristics. |

### 1.2 Out of scope for v1

The following PDU families are explicitly excluded. Each may be reconsidered
in v2; the rationale for exclusion is recorded so future scope conversations
have a starting point.

| PDU family | IEEE 1278.1 § | Excluded because |
|---|---|---|
| Collision | § 5.4.5 | v1 does not model contact mechanics; collisions are abstracted into Detonation outcomes when relevant. |
| Service Request, Resupply Offer / Received / Cancel, Repair Complete / Response | § 5.5 | v1 has no logistics modeling. |
| Action Request / Response, Data Query, Data, Set Data, Event Report, Comment | § 5.6 | Simulation management traffic is handled out-of-band by the control plane (WS-301). |
| Designator | § 5.7.4 | Laser designation is below v1's effect granularity. |
| Electromagnetic Emission | § 5.7.3 | Emission patterns are summarized in Transmitter PDUs for v1; full emission modeling is deferred. |
| IFF | § 5.7.6 | Identification is handled by the neutral schema's `force_affiliation` field; IFF interrogation is not modeled. |
| Underwater Acoustic | § 5.7.5 | No maritime acoustic modeling in the Nashville theater. |
| Minefield, Synthetic Environment, Logistics, Live Entity | § 5.10–§ 5.13 | Out of v1 scope. |

If a federate sends an out-of-scope PDU to the adapter, the adapter logs and
discards it (no neutral-schema event is created). This is documented as
lossy but acceptable for v1.

### 1.3 Exercise / Site / Application identifier mapping

DIS identifies entities and events with `EntityID = (Site, Application,
EntityNumber)` triples (§ 6.2.28) and groups traffic by an `ExerciseID`
byte (§ 6.2.31). The neutral schema uses UUIDs for both `entity_id` and
`event_id` and namespaces by `(tenant_id, scenario_id)`. The adapter
translates as follows:

| DIS field | Neutral source | Translation rule |
|---|---|---|
| `ExerciseID` (1 byte, `1..255`) | `scenario_id` | Adapter maintains a `(tenant_id, scenario_id) → ExerciseID` lookup table allocated at scenario start. ExerciseID `0` is reserved (DIS convention). 255 active scenarios per adapter instance is the v1 ceiling — flagged as an open question if scenarios-per-tenant exceeds this. |
| `Site` (16-bit) | `tenant_id` (low 16 bits of a deterministic hash) | Adapter assigns `Site` from a hash of `tenant_id` modulo `2^16 - 1`. Site `0` is reserved. Collisions (>65k tenants) are deferred. |
| `Application` (16-bit) | adapter-instance ordinal | Each adapter process within a tenant gets a unique Application id. Single-process v1: hardcoded to 1. |
| `EntityNumber` (16-bit) | `entity_id` (sequence per scenario) | Adapter maintains an `entity_id → EntityNumber` table per `(Site, Application, ExerciseID)`. `EntityNumber = 0` is reserved (DIS) and never assigned. |

**Round-trip note:** the UUID → `(Site, App, EntityNumber)` mapping is
stateful. The adapter MUST persist the mapping table; otherwise round-tripping
through DIS and back produces a different UUID. Persistence layer: deferred
to the adapter implementation issue.

---

## 2. Conventions

### 2.1 Coordinate systems

The neutral schema stores both geodetic (`position_lat_deg`,
`position_lon_deg`, `position_alt_m`) and ECEF
(`position_ecef_x_m/y_m/z_m`) per WS-101 § Conventions. DIS PDUs use ECEF
exclusively for entity location (§ 6.2.43) and a fixed-point geocentric
representation for some fields. The adapter:

- Reads ECEF directly from the neutral schema; no recomputation.
- Velocity is already ECEF in the neutral schema (m/s) — direct copy.
- Orientation in the neutral schema is a unit quaternion; DIS uses Euler
  angles (psi, theta, phi in radians, § 6.2.32). Adapter converts
  quaternion → Euler at the write boundary. The reverse conversion on read
  introduces small numerical drift; flagged in [§ 5.4](#54-orientation-conversion-drift).

### 2.2 Time

DIS timestamps use a 32-bit field with a "relative" / "absolute" bit
(§ 6.2.88). The neutral schema uses UTC `timestamptz` with microsecond
precision. Adapter uses **absolute timestamps** from scenario start in DIS
(time origin = `scenario.start_at` from the control plane). Sub-second
resolution: DIS timestamp lower 31 bits map to (time-units of 1.6 µs).
Adapter rounds neutral microseconds to the nearest 1.6 µs unit; flagged in
[§ 5.5](#55-timestamp-quantization).

### 2.3 Force / affiliation

Neutral `force_affiliation ∈ {BLUE, RED, WHITE, NEUTRAL}` maps to the
DIS `Force ID` byte (§ 6.2.17):

| Neutral | DIS Force ID | Notes |
|---|---|---|
| `BLUE` | `1 (Friendly)` | |
| `RED` | `2 (Opposing)` | |
| `NEUTRAL` | `3 (Neutral)` | |
| `WHITE` | `0 (Other)` | DIS has no canonical white-cell affiliation; mapped to `Other`. Round-trip is lossy: `WHITE → 0 → ?`. The receive-side adapter MUST preserve the source of `Other` PDUs out-of-band (e.g., from federate metadata) to round-trip correctly. |

### 2.4 Entity type

The neutral schema uses two layers: `type_category` (enum) and
`type_subtype_ref` (free-form taxonomy reference). DIS uses an
`Entity Type` record with seven sub-fields (`Kind`, `Domain`, `Country`,
`Category`, `Subcategory`, `Specific`, `Extra` — § 6.2.30).

The adapter resolves the mapping through a lookup table keyed on the
neutral `type_subtype_ref`. The table is authored and committed alongside
this contract in v1 — see [§ 6 Open questions](#6-open-questions); for now,
the adapter falls back to a placeholder `Entity Type` with category-only
information when the subtype is unknown. **All such fallbacks are logged and
emitted as `czml_rejected`-style audit events on the kernel side** (per
WS-503's adjacent rejection-event pattern).

---

## 3. Entity → Entity State PDU

A WS-101 entity row projects to one Entity State PDU per heartbeat. The
adapter publishes Entity State at a configurable rate (default: 5 Hz for
moving entities, 0.2 Hz for static).

### 3.1 Field mapping

| Neutral field | Entity State PDU field | IEEE § | Notes |
|---|---|---|---|
| `entity_id` | `Entity ID` (Site, App, EntityNumber) | § 6.2.28 | Via the translation table (§ 1.3). |
| `force_affiliation` | `Force ID` | § 6.2.17 | Per [§ 2.3](#23-force--affiliation). |
| `type_category` + `type_subtype_ref` | `Entity Type` | § 6.2.30 | Via the type lookup table; lossy fallback flagged. |
| `position_ecef_x_m / y_m / z_m` | `Entity Location` | § 6.2.43 | Direct copy. |
| `velocity_ecef_vx_mps / vy_mps / vz_mps` | `Entity Linear Velocity` | § 6.2.69 | Direct copy. |
| `orientation_qw / qx / qy / qz` | `Entity Orientation` (psi, theta, phi) | § 6.2.32 | Quaternion → Euler conversion. |
| `display_name` | `Marking` (12 ASCII chars) | § 6.2.79 | Truncated if longer than 12 chars; truncation logged. |
| (none — derived) | `Capabilities` (bitfield) | § 6.2.13 | Derived from the entity's `capability_set_ref` (WS-106) at projection time. v1 maps a small subset (ammunition supply, fuel supply, repair) — all others zero. |
| (none — derived) | `Dead Reckoning Parameters` | § 6.2.18 | Defaults to algorithm `2 (DRM_F_P_W)` (constant velocity, no rotation). Higher-fidelity DR algorithms are an open question. |
| (none — fixed) | `Articulation Parameters` | § 6.2.5 | None in v1 (no turret / antenna articulation modeled). |

### 3.2 Lifecycle

- **Entity created** (new row in neutral `entities`): adapter assigns
  `EntityNumber`, publishes one Entity State PDU.
- **Entity updated** (row update — position / velocity / orientation /
  capability change): adapter publishes Entity State PDU within the
  heartbeat window; if the change exceeds DR thresholds, publishes
  immediately.
- **Entity removed** (soft-delete): adapter sets the appearance bit
  `Deactivated` (§ 6.2.7) and publishes one final Entity State PDU. DIS has
  no separate deletion PDU; the federate is expected to time out the entity
  after a configurable interval (default 12 seconds).

### 3.3 Open questions

- Dead-reckoning algorithm choice per `entity_type_category` — currently
  fixed at `DRM_F_P_W`, but `MARITIME_UNIT` typically wants `DRM_R_V_W`.
- Articulation parameters for `PLATFORM` entities with rotating turrets:
  not in v1 schema; would require a `turret_azimuth_deg` extension to
  WS-101.

---

## 4. Event → action PDUs

Event-bearing PDUs (Fire, Detonation, Signal, Transmitter, Receiver) project
from neutral `events` rows. The mapping is keyed on `(source_officer_type,
action_verb)`.

### 4.1 Verb-to-PDU summary

| Officer | Verb | PDU(s) | Notes |
|---|---|---|---|
| EFFECTOR | `engage` | Fire (+ later Detonation) | Fire at issue, Detonation at simulated impact time. |
| EFFECTOR | `suppress` | Fire (+ Detonation, but burst munition with `Munition Descriptor.Quantity > 1`) | Suppression encoded as a multi-round burst. |
| EFFECTOR | `destroy` | Fire + Detonation | Destroy outcome encoded in `Detonation Result` (§ 6.2.27). |
| EFFECTOR | `disable` | Fire + Detonation | `Detonation Result` carries `Mobility Kill` or `Firepower Kill` per payload. |
| COMMUNICATOR | `send` | Signal | Application-level message in `Data` octet array. |
| COMMUNICATOR | `relay` | Signal | Same as `send`; the relay metadata rides as application-level header inside `Data`. |
| COMMUNICATOR | `report` | Signal | Same as `send`; payload header indicates report type. |
| COMMUNICATOR | `jam` | Transmitter (active continuous) | One Transmitter PDU at jam start; Transmitter "off" PDU at jam end. |
| SENSOR | `detect` | Receiver (one-shot) | Receiver PDU with detected emission characteristics; the detected entity is identified via `Transmitter Entity ID` cross-reference. |
| SENSOR | `track` | Receiver (continuous) | Periodic Receiver PDUs while the track is active. |
| SENSOR | `classify` | Receiver (one-shot, with classification metadata) | Carries the classification verdict in application-level data inside the Receiver PDU's variable-length record. |
| SENSOR | `lose_track` | (none) | DIS has no canonical "track lost" PDU. Modeled as cessation of Receiver heartbeats. **Lossy** — see [§ 5.1](#51-lose_track-not-representable). |
| MOVER | `move_to` / `follow_route` / `halt` / `assume_posture` | (none — Entity State only) | Movement is fully expressed via Entity State updates per § 3.2. **Lossy** for `assume_posture` semantics — see [§ 5.2](#52-assume_posture-loses-semantic). |
| COMMANDER | `issue_order` / `request_support` / `delegate` / `escalate` | Signal (with C2 application header) | Command traffic rides Signal PDUs as application-level data. **Lossy** — verb identity is preserved only in payload, not in PDU semantics. See [§ 5.3](#53-commander-verbs-collapse-to-signal). |

### 4.2 Fire PDU mapping (Effector verbs)

| Neutral source | Fire PDU field | IEEE § | Notes |
|---|---|---|---|
| `event_id` | `Event ID` (Site, App, EventNumber) | § 6.2.34 | Adapter maintains an `event_id → EventNumber` mapping per scenario, analogous to entity numbers. |
| `source_entity_id` | `Firing Entity ID` | § 6.2.28 | Translated through entity ID table. |
| `payload.target_entity_id` | `Target Entity ID` | § 6.2.28 | Required for `engage` / `destroy` / `disable`; optional for `suppress` (suppression of an area, not an entity). When the target is an area, `Target Entity ID` is set to `NO_ENTITY` (`0,0,0`) and the impact location is conveyed in `Location In World Coordinates`. |
| `payload.munition_type_ref` | `Munition Descriptor.Munition Type` | § 6.2.20 | Lookup table from neutral munition reference to DIS Munition Type (Kind=2 Munition). Same authoring problem as Entity Type lookup. |
| `payload.burst_count` (default 1) | `Munition Descriptor.Quantity` | § 6.2.20 | Suppression bursts use values >1. |
| `payload.range_m` | `Range` | § 6.2.71 | Effective firing range in meters. |
| `payload.impact_lat_deg / lon_deg / alt_m` | `Location In World Coordinates` (ECEF) | § 6.2.43 | Adapter computes ECEF from geodetic at projection time. |
| `ts` | `Timestamp` (PDU header) | § 6.2.88 | Per [§ 2.2](#22-time). |

### 4.3 Detonation PDU mapping

A Detonation PDU is emitted at the simulated time of impact. The kernel
emits a follow-on event with `causal_predecessors = [fire_event_id]`; the
adapter projects that event to a Detonation PDU.

| Neutral source | Detonation PDU field | IEEE § | Notes |
|---|---|---|---|
| `event_id` of the originating Fire | `Event ID` | § 6.2.34 | Same Event ID as the Fire PDU — the round is the same simulation event. |
| `payload.firing_entity_id` | `Firing Entity ID` | § 6.2.28 | Carried forward from the Fire event. |
| `payload.target_entity_id` | `Target Entity ID` | § 6.2.28 | As above; `NO_ENTITY` for area effects. |
| `payload.impact_*` | `Location In World Coordinates` | § 6.2.43 | Final impact, ECEF. |
| `payload.detonation_result` | `Detonation Result` | § 6.2.27 | Mapped from neutral `result` enum (`hit`, `miss`, `target_destroyed`, `mobility_kill`, `firepower_kill`, `mobility_firepower_kill`) to the DIS enumeration. |
| `payload.variable_parameters` | `Variable Parameters` (array) | § 6.2.94 | Reserved for fragment / debris articulation; usually empty in v1. |

### 4.4 Signal PDU mapping (Communicator + Commander)

| Neutral source | Signal PDU field | IEEE § | Notes |
|---|---|---|---|
| `source_entity_id` | `Entity ID` | § 6.2.28 | Originator of the message. |
| `payload.radio_id` | `Radio ID` | § 6.2.74 | The originator's logical radio. v1 default: `1` if the entity has only one radio. |
| `payload.encoding_class` | `Encoding Scheme` | § 6.2.29 | Default: `1 (encoded audio)` for `send` / `relay`; `4 (application-specific data)` for `report` / Commander verbs. |
| `payload.tdl_type` | `TDL Type` | § 6.2.86 | `0 (Other)` unless the scenario uses Link 16 modeling (out of v1 scope). |
| `payload.sample_rate` | `Sample Rate` | (header) | `0` for application-specific data. |
| `payload.data` | `Data` (variable octet array) | (header) | Application payload. Commander verbs carry a 4-byte verb header at the start of `Data` so receivers can dispatch on verb identity. **Round-trip note:** if a federate strips the verb header, the verb identity is lost. |

### 4.5 Transmitter PDU mapping (Communicator.jam, active sensors)

| Neutral source | Transmitter PDU field | IEEE § | Notes |
|---|---|---|---|
| `source_entity_id` | `Entity ID` | § 6.2.28 | The emitting platform. |
| `payload.radio_id` | `Radio ID` | § 6.2.74 | Logical emitter on the platform. |
| `payload.transmit_state` | `Transmit State` | § 6.2.91 | `0=off`, `1=on but not transmitting`, `2=on and transmitting`. Jam start: `2`. Jam end: `0`. |
| `payload.frequency_hz` | `Frequency` | (header, double) | Hz. |
| `payload.bandwidth_hz` | `Transmit Frequency Bandwidth` | (header) | |
| `payload.power_dbm` | `Power` | (header) | Decibel-milliwatts. |
| `payload.modulation` | `Modulation Type` | § 6.2.59 | Default major modulation: `9 (Spread Spectrum)` for jamming; `1 (Amplitude)` for voice; `2 (Angle)` for FM. |
| `payload.antenna_pattern` | `Antenna Pattern` | § 6.2.9 | v1 uses pattern type `0 (omnidirectional)` for jam-circle effects; directional patterns are open. |

### 4.6 Receiver PDU mapping (Sensor verbs)

| Neutral source | Receiver PDU field | IEEE § | Notes |
|---|---|---|---|
| `source_entity_id` | `Entity ID` | § 6.2.28 | Receiving platform. |
| `payload.radio_id` | `Radio ID` | § 6.2.74 | Logical receiver. |
| `payload.received_power_dbm` | `Received Power` | (header) | dBm. |
| `payload.transmitter_entity_id` | `Transmitter Entity ID` | § 6.2.28 | The detected emitter (resolves the "what was detected" link). |
| `payload.transmitter_radio_id` | `Transmitter Radio ID` | § 6.2.74 | |
| `payload.receiver_state` | `Receiver State` | § 6.2.73 | `0=off`, `1=on but not receiving`, `2=on and receiving`. |
| `payload.classification` (verb=`classify` only) | (variable-length application data appended to PDU) | — | Classification verdict + confidence ride as application-level data. |

---

## 5. Lossy mappings

The following mappings are known-lossy. Producers and consumers MUST accept
that round-tripping neutral → DIS → neutral does not preserve the lost
information unless out-of-band metadata is also carried.

### 5.1 `lose_track` not representable

DIS has no canonical "track lost" PDU. The neutral verb is modeled as the
cessation of Receiver PDU heartbeats, which means a federate that observes
the kernel's stream cannot distinguish "track lost" from "kernel stalled."

Mitigation (deferred): emit an Application-specific Signal PDU with a
known `Encoding Scheme = 4` and a bespoke header byte indicating
`track-lost`. Open question — see [§ 6](#6-open-questions).

### 5.2 `assume_posture` loses semantic

A posture change (e.g., `dismount`, `dig_in`, `move_to_overwatch`) affects
the entity's capability profile but is invisible in DIS unless reflected
in `Entity Appearance` bits (§ 6.2.7). The Appearance bitfield is finite
and platform-specific; not all neutral postures map to existing bits.

Mitigation: postures that map to canonical bits (e.g.,
`PLATFORM_LIFE_FORM_HATCH = OPEN/CLOSED`) project; others are dropped
from the wire and only visible to consumers that read the kernel directly.

### 5.3 Commander verbs collapse to Signal

`issue_order`, `request_support`, `delegate`, `escalate` all project to
Signal PDUs with the same `Encoding Scheme`. The verb identity is
preserved only in the application-level header inside `Data`. A federate
that strips the header sees four indistinguishable command messages.

### 5.4 Orientation conversion drift

Quaternion → Euler → quaternion round-trip introduces ≤ 1e-6 error per
component. Acceptable for v1 visual rendering; flagged for any future
high-fidelity coupling.

### 5.5 Timestamp quantization

DIS timestamps quantize to ~1.6 µs ticks. Neutral microsecond timestamps
are rounded; pairs of events less than 1.6 µs apart can collapse to the
same DIS timestamp. v1 simulation cadence is multi-second-per-turn so this
is academic, but flagged for completeness.

### 5.6 Tenant / scenario address collisions

`Site = hash(tenant_id) mod 65535` collides at >65k tenants per adapter
process. `ExerciseID` is 1 byte and can address 254 scenarios per tenant.
Both ceilings are far above v1 demo scope but become real problems at
production scale.

---

## 6. Open questions

1. **Munition type taxonomy.** The Fire PDU `Munition Descriptor` requires
   a DIS Munition Type. The neutral schema treats munition references as
   opaque labels (per WS-101). A munition lookup table needs to be
   authored — owner: kernel side, sized for v1 effect families per
   WS-108. Tentative path: `kernel/schema/dis-munition-types.json`.
2. **Entity type lookup table** — same shape as the munition table, sized
   to the entity subtypes used by WS-107 capability profiles. Tentative
   path: `kernel/schema/dis-entity-types.json`.
3. **Dead-reckoning algorithm per category** — defaulting all to
   `DRM_F_P_W` (§ 6.2.18) may produce visible drift on maritime entities.
   Decide before any maritime entities enter v1 scope.
4. **`lose_track` representation** — define an application-level Signal
   PDU header byte for track-lost, OR accept the cessation-of-heartbeats
   modeling. Decision needed before WS-503 (live adapter) renders sensor
   tracks.
5. **WHITE force round-trip** — `WHITE → 0 (Other) → ?`. Either widen
   `force_affiliation` enum on read with a sentinel, or carry side-channel
   metadata. Defer to WS-103 (HLA) review since HLA has the same problem.
6. **Articulation Parameters for turreted platforms** — requires a
   `turret_azimuth_deg` (and possibly `elevation`) field on entity rows.
   Out of v1 schema; track as a WS-101 amendment proposal.
7. **Persistence of the UUID ↔ (Site, App, EntityNumber) table** — the
   adapter is stateful. Where does this live? Options: the per-tenant
   Postgres instance (WS-301), Redis (already used by WS-304), or a flat
   file checkpointed per scenario start. Decide at adapter implementation
   time.
8. **Heartbeat rate per entity category** — defaults of 5 Hz / 0.2 Hz are
   guesses. Validate against renderer frame budget once WS-503 lands.

---

## 7. Round-trip expectations

For every PDU family in scope, the adapter MUST round-trip the in-scope
neutral fields losslessly modulo the [§ 5](#5-lossy-mappings) exceptions.

A regression suite at adapter implementation time should:

1. Generate a synthetic neutral entity / event row.
2. Project to the corresponding DIS PDU via the adapter.
3. Project back to neutral via the inverse adapter.
4. Assert structural equality on all in-scope fields except those flagged
   lossy in § 5.

Suite scope is non-blocking for this contract; tracked for the WS-503 era.

---

## 8. References

- IEEE Std 1278.1-2012, Distributed Interactive Simulation — Application
  Protocols (procurement: <https://standards.ieee.org/ieee/1278.1/4949/>).
  No copyrighted text reproduced here; section numbers cited only.
- Public summary of DIS PDU structure (SISO):
  <https://www.sisostandards.org/page/DigitalLibraryProductDIS>.
- Open-DIS reference implementation (BSD-licensed, useful for field byte
  layouts): <https://github.com/open-dis/open-dis-python>.
- Neutral schema: [`docs/schema/entity-event.md`](entity-event.md) (WS-101).
- HLA adapter contract (parallel): WS-103 (#7).
- Glossary — officer types and verb assignments:
  [`docs/glossary.md#1-officer-types`](../glossary.md#1-officer-types).
