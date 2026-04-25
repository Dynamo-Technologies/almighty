# Almighty — Effect artifact taxonomy (v1)

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

An **artifact** is the persistent record of an effect or non-spatial
output produced by an officer-verb commit. Every CZML packet shown to
the renderer corresponds to a spatial artifact; non-spatial artifacts
(orders, reports, comms traffic, intel assessments) live in the kernel
and surface in the EXCON consoles, AAR replay, and adjudication queue
without a CZML binding.

This document is the canonical taxonomy. It locks:

- The base artifact shape — fields shared by every artifact regardless
  of subtype.
- The five-state adjudication state machine.
- Nine spatial artifact subtypes, one per glossary effect family.
- Four non-spatial subtypes (Order, Report, Comms traffic, Intel
  assessment) with the verb-emission rules that produce each.
- The canonical verb → artifact emission table.

Cross-references:

- Base events: [`entity-event.md`](entity-event.md) (WS-101).
- Verb signatures and emission side-effects:
  [`officer-interfaces.md`](officer-interfaces.md) (WS-105).
- Capability profile referenced by every artifact:
  [`capability-profiles.md`](capability-profiles.md) (WS-106).
- Effect families and non-spatial type definitions:
  [`docs/glossary.md` § 2](../glossary.md#2-effect-families).

---

## 1. Base artifact

Every artifact, spatial or non-spatial, carries the same base fields.

| Field | Type | Required | Notes |
|---|---|---|---|
| `artifact_id` | `uuid` | yes | Primary key. UUID v4. |
| `tenant_id` | `uuid` | yes | Namespace boundary; matches the source event. |
| `scenario_id` | `uuid` | yes | Namespace boundary; matches the source event. |
| `subtype` | enum `artifact_subtype` | yes | One of the 13 subtypes (9 spatial + 4 non-spatial) defined in [§ 4](#4-spatial-artifact-subtypes) and [§ 5](#5-non-spatial-artifact-subtypes). |
| `source_event_id` | `uuid` | yes | FK to `events.event_id` (WS-101). The verb that produced this artifact. |
| `owning_entity_id` | `uuid` | yes | FK to `entities.entity_id` (WS-101). Usually equals `events.source_entity_id` of the source event, but is captured separately so artifact ownership survives source-event archival. |
| `capability_profile_ref` | `string` | yes | `"<profile_id>@<version>"` per WS-101 convention; the capability profile that gated emission. AAR uses this to render which profile authorized the artifact. |
| `time_validity_start` | `timestamptz` | yes | Inclusive lower bound on the artifact's wall-clock validity. |
| `time_validity_end` | `timestamptz` | yes | **Exclusive** upper bound. The artifact is no longer rendered or considered active at or after this instant. |
| `czml_template_binding` | `text` | conditional | CZML template name from WS-201 (e.g., `radar-fan`). REQUIRED for spatial subtypes; MUST be `null` for non-spatial. |
| `adjudication_state` | enum `adjudication_state` | yes | One of `proposed`, `accepted`, `rejected`, `contested`, `resolved`. See [§ 2](#2-adjudication-state-machine). |
| `adjudication_history` | `jsonb[]` | yes | Append-only log: `[{state, decided_by, rationale, ts}, ...]`. Initial entry on emission has `state="proposed"`. AAR (WS-506) replays this. |
| `payload` | `jsonb` | yes | Subtype-specific fields. Schema per subtype defined in [§ 4](#4-spatial-artifact-subtypes) and [§ 5](#5-non-spatial-artifact-subtypes). |
| `created_at` | `timestamptz` | yes | Default `now()`. |

### 1.1 Constraints

1. `(tenant_id, scenario_id, artifact_id)` is the natural lookup key.
   `artifact_id` alone is unique globally (UUID v4 collision is the bound).
2. `source_event_id` MUST reference an event in the same
   `(tenant_id, scenario_id)` namespace.
3. `time_validity_end > time_validity_start` (strictly).
4. `czml_template_binding IS NULL` iff `subtype` is non-spatial. Enforced
   by a CHECK constraint in the migration that lands with WS-301.
5. `adjudication_history` is append-only. The kernel write path appends
   new entries; existing entries are immutable.
6. The terminal states `accepted`, `rejected`, and `resolved` are
   absorbing — once reached, no further transitions. `contested` may
   loop back through `resolved`. See [§ 2](#2-adjudication-state-machine).

### 1.2 Indexes

The artifacts table inherits the namespace pattern from WS-101:

- PK on `artifact_id`.
- Composite index on `(tenant_id, scenario_id, time_validity_start)`
  for AAR timeline scans (WS-506).
- Composite index on `(tenant_id, scenario_id, source_event_id)` for
  "all artifacts produced by this event" lookups.
- Composite index on `(tenant_id, scenario_id, owning_entity_id)` for
  EXCON sidebar listings (WS-504).
- Partial index on `(tenant_id, scenario_id) WHERE adjudication_state IN
  ('proposed', 'contested')` for the white cell review queue (WS-505).

---

## 2. Adjudication state machine

```
                +--------+
                | (none) |
                +--------+
                     |
                     | emit (officer tool, gated by validator)
                     v
              +----------+
   +--------> | proposed |---------+
   |          +----------+         |
   |               |               |
   |  contest      | accept        | reject
   |               |               |
   |               v               v
+-----------+   +----------+   +----------+
| contested |<--+ accepted |   | rejected |   (terminal)
+-----------+   +----------+   +----------+
   |    ^          (terminal)
   |    |
   |    | re-contest after resolution
   |    |
   |    +---------------+
   |                    |
   | resolve            |
   v                    |
+----------+            |
| resolved |------------+
+----------+
   (terminal in v1; the kernel does not auto-loop. A fresh `contested`
    requires a new override decision per WS-303.)
```

State definitions:

| State | Meaning | Set by |
|---|---|---|
| `proposed` | The verb committed and the artifact was created, but the override gateway has not yet released it for rendering. | Kernel write path on commit. |
| `accepted` | The override gateway approved (or auto-approved) the artifact. The renderer (WS-503) starts rendering at `time_validity_start`. | Override gateway (WS-303), per policy or manual decision. |
| `rejected` | The override gateway blocked the artifact. The kernel keeps the row for AAR but the renderer never receives the CZML packet. | Override gateway, per policy or manual block. |
| `contested` | A subsequent event or operator action has called the artifact's accuracy or correctness into question. The white cell adjudicator (WS-405) is responsible for proposing a `resolved` outcome. | Override gateway or adjudicator, per WS-405 logic. |
| `resolved` | A contested artifact has been resolved by the adjudicator (auto-resolved if low/medium stakes, human-resolved if high). The `payload.resolution` block records the outcome. | White cell adjudicator (WS-405) or human via WS-505. |

Transitions are recorded in `adjudication_history`. Each entry has
`{state, decided_by, rationale, ts}` where `decided_by` is the agent or
operator id that effected the transition.

---

## 3. Adjudication flow categories

Each artifact subtype declares a default adjudication flow. The override
gateway (WS-303) consults the flow to decide whether `proposed` →
`accepted` requires a manual click-through, an auto-decision, or is
permanently held.

| Flow | Behavior |
|---|---|
| `auto-accept` | The gateway transitions `proposed` → `accepted` immediately at commit. No human is in the loop. Used for routine, low-stakes artifacts (most sensor artifacts, comms traffic). |
| `review` | The gateway leaves the artifact in `proposed` and publishes to the `override_pending` WebSocket channel (per WS-303). A white cell operator decides via the WS-505 console. The default override scope (per [`docs/glossary.md` § 5.4](../glossary.md#composability-rule)) maps an empty policy table to this flow. |
| `always-contested` | The artifact is committed in `proposed` AND a `contested` entry is appended immediately to `adjudication_history`. The adjudicator (WS-405) flags `human_required = true`. The gateway holds rendering until a white cell operator resolves via WS-505. Used for irreversible high-stakes artifacts (`destroy`-emitted, civilian-area effects). |

The flow declared on the subtype is the **default**; an override policy
(WS-303) may strengthen the flow (`auto-accept` → `review` →
`always-contested`) on a per-event, per-agent-per-turn, or per-turn
basis. Policies cannot weaken the flow — `always-contested` is a
floor, not a ceiling.

---

## 4. Spatial artifact subtypes

Each spatial subtype binds to one CZML template (WS-201) and projects
its parameters to that template's `params` block. The
`capability_constraints` on the template plus the
`effect_parameter_ranges` on the emitting entity's capability profile
(WS-106) bound every numeric field; the validator (WS-202) enforces both
at emission time.

Conventions inside `payload` blocks below:

- All coordinates are WGS-84 (`lat_deg`, `lon_deg`, `alt_m`).
- All angles are degrees unless noted.
- All physical units are SI (m, m/s, watts, seconds).

### 4.1 `ew_cone`

Directional electronic-warfare emission: passive ELINT detection cone or
directional active jamming.

**Emitted by:**

- `Sensor.detect` with `modality = RF` — passive ELINT cone of detection.
- `Communicator.jam` when the emitting entity's effector profile has
  `delivery_mode = EW` AND the platform is single-aperture directional
  (validator decides; default is omni → `jamming_circle`).

**Payload fields (in addition to base):**

| Field | Type | Required | Notes |
|---|---|---|---|
| `origin` | `{lat_deg, lon_deg, alt_m}` | yes | Apex of the cone. Owning entity's position at emission. |
| `azimuth_deg` | `float` | yes | Bearing of the cone's centerline; `[0, 360)`. |
| `beamwidth_deg` | `float` | yes | Full angular width; `[5, 60]` per profile. |
| `effective_range_m` | `float` | yes | Cone slant range. |
| `band` | enum `rf_band` | conditional | Required when source is `Communicator.jam`; optional for `Sensor.detect` (defaults to "broadband"). |

**CZML template:** `ew-cone`.

**Adjudication flow:** `auto-accept` for sensor-emitted (passive ELINT
is observation, not an effect). `review` for jam-emitted (EW posture
changes are operator-visible).

**Time validity:** `start = source_event.ts`; `end = start +
profile.communicator.bands.<band>.<duration>` (jam) or `+ 60s` (sensor).

### 4.2 `uas_corridor`

Unmanned aircraft system flight corridor or comms relay corridor.

**Emitted by:**

- `Communicator.relay` when the emitting entity is airborne AND
  `profile.communicator.advertise_corridor = true`. The corridor spans
  the relay path between source and recipient at the entity's altitude.

**Payload fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `polyline` | `[{lat_deg, lon_deg}, ...]` | yes | Corridor centerline; ≥ 2 points. |
| `altitude_band_lower_m` | `float` | yes | |
| `altitude_band_upper_m` | `float` | yes | |
| `width_m` | `float` | yes | Half-width of the corridor on either side of the centerline. |

**CZML template:** `uas-corridor`.

**Adjudication flow:** `auto-accept`. Corridors are advisory, not
effects.

**Time validity:** scenario-config-driven; defaults to source event's
turn duration.

### 4.3 `radar_fan`

Radar coverage volume.

**Emitted by:**

- `Sensor.detect` with `modality = RADAR`.
- `Sensor.track` with `modality = RADAR` (continuation).

**Payload fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `origin` | `{lat_deg, lon_deg, alt_m}` | yes | |
| `azimuth_deg` | `float` | yes | Centerline bearing. |
| `sweep_arc_deg` | `float` | yes | Total sweep arc; `[5, 360]`. |
| `range_m` | `float` | yes | Effective detection range. |
| `elevation_deg` | `float` | optional | Tilt above horizontal; default 0. |

**CZML template:** `radar-fan`.

**Adjudication flow:** `auto-accept`. Radar emission is observable but
not an effect for v1 adjudication purposes (separate emission
modeling is out of scope, see WS-102/WS-103 open questions).

**Time validity:** start at source event; end at the next `track`
update or `lose_track` for the same target.

### 4.4 `jamming_circle`

Omnidirectional jamming volume.

**Emitted by:**

- `Communicator.jam` (default for omni-aperture platforms).

**Payload fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `center` | `{lat_deg, lon_deg, alt_m}` | yes | Owning entity's position at emission. |
| `radius_m` | `float` | yes | Effective radius; bounded by profile. |
| `power_w` | `float` | yes | Effective radiated power; bounded by profile. |
| `band` | enum `rf_band` | yes | |
| `polygon_declared` | `[[lat_deg, lon_deg], ...]` | optional | The polygon the agent originally requested. The validator may shrink the declared polygon to a circumscribing circle for single-aperture platforms — both are kept for AAR. |

**CZML template:** `jamming-circle`.

**Adjudication flow:** `review` (default). Promoted to `always-contested`
when the polygon overlaps a civilian RF band declared in scenario
config (per WS-105 § Communicator.jam adjudication note).

**Time validity:** `start = source_event.ts`; `end = start +
payload.duration_s` (from the source event's payload).

### 4.5 `satellite_swath`

Transient ground footprint of an overhead pass.

**Emitted by:**

- `Sensor.detect` or `Sensor.track` when the owning entity has
  `entities.type_category = SPACE_UNIT` (per WS-101 enum). No additional
  verb is needed; the entity type is the trigger.

**Payload fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `pass_start_coordinate` | `{lat_deg, lon_deg}` | yes | Ground track entry. |
| `pass_end_coordinate` | `{lat_deg, lon_deg}` | yes | Ground track exit. |
| `swath_width_m` | `float` | yes | Cross-track ground footprint. |
| `pass_duration_s` | `float` | yes | Wall-clock duration of the pass. |

**CZML template:** `satellite-swath`.

**Adjudication flow:** `auto-accept`. Satellite passes are predictable
and rarely contested in v1 scope.

**Time validity:** spans the pass; `start = entry-time`, `end =
entry-time + pass_duration_s`.

### 4.6 `indirect_fire_arc`

Ballistic trajectory plus impact polygon.

**Emitted by:**

- `Effector.engage` when `weapon_system.delivery_mode = INDIRECT`.
- `Effector.suppress` (always — suppression is area-effect indirect).
- `Effector.destroy` when `weapon_system.delivery_mode = INDIRECT`.
- `Effector.disable` when `method = KINETIC` and
  `weapon_system.delivery_mode = INDIRECT`.

**Payload fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `firing_point` | `{lat_deg, lon_deg, alt_m}` | yes | |
| `impact_point` | `{lat_deg, lon_deg, alt_m}` | yes | |
| `dispersion_ellipse_a_m` | `float` | yes | Semi-major axis at impact. |
| `dispersion_ellipse_b_m` | `float` | yes | Semi-minor axis. |
| `time_of_flight_s` | `float` | yes | |
| `mode` | enum `indirect_fire_mode` | yes | One of `engage`, `suppress`, `destroy`, `disable`. Drives renderer styling. |
| `volume_count` | `int` | yes | Mirror of source event's `volume_count`. |

**CZML template:** `indirect-fire-arc`.

**Adjudication flow:**

- `auto-accept` when `mode = suppress` AND target is not a population
  area (scenario config flag).
- `review` when `mode = engage` AND `force_affiliation = NEUTRAL` for
  any entity in the dispersion ellipse.
- `always-contested` when `mode = destroy`. By design — `destroy` is
  always high-stakes per WS-105 § Effector.destroy.

**Time validity:** `start = source_event.ts`; `end = start +
time_of_flight_s + post_impact_render_s` (default 30s).

### 4.7 `ir_plume`

Vertical infrared signature.

**Emitted by:**

- `Effector.destroy` (always emitted as a follow-on to the
  `indirect_fire_arc`; one source event produces both artifacts).
- `Effector.disable` when `method = KINETIC` (smaller plume; the
  `peak_intensity_w_per_sr` is bounded lower by the profile).

**Payload fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `location` | `{lat_deg, lon_deg, alt_m}` | yes | Equals the originating arc's `impact_point`. |
| `peak_intensity_w_per_sr` | `float` | yes | |
| `decay_s` | `float` | yes | Decay-curve total duration. |

**CZML template:** `ir-plume`.

**Adjudication flow:** inherits from the originating
`indirect_fire_arc`. If the arc is `always-contested`, the plume is
also `always-contested`. The white cell decides them as a pair.

**Time validity:** `start = arc.time_validity_start + time_of_flight_s`
(the moment of impact); `end = start + decay_s`.

### 4.8 `masint_cell`

Bounded measurement-and-signature-intelligence collection cell.

**Emitted by:**

- `Sensor.detect` with `modality ∈ {ACOUSTIC, SEISMIC, MASINT_MULTI}`.
- `Sensor.classify` when the prior detection's modality is in the same
  set (refines the cell into a tighter polygon).

> **Naming reminder:** the term is **MASINT** (Measurement And Signature
> Intelligence). The form "Mzent" is a transcription error and MUST NOT
> appear in code, payloads, or comments. See
> [`docs/glossary.md` § 2 MASINT cell](../glossary.md#masint-cell).

**Payload fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `polygon` | `[[lat_deg, lon_deg], ...]` | yes | Closed ring; min 4 points (3 + closure repeat). |
| `signal_type` | enum `masint_signal` | yes | One of `ACOUSTIC`, `SEISMIC`, `RF`, `MULTI`. |
| `dwell_s` | `float` | yes | Collection dwell window. |

**CZML template:** `masint-cell`.

**Adjudication flow:** `auto-accept`.

**Time validity:** `start = source_event.ts`; `end = start + dwell_s`.

### 4.9 `keyhole_footprint`

Refined polygonal footprint produced when overlapping ISR observations
correlate.

**Emitted by:**

- `Sensor.classify` (always — per WS-105 § Sensor.classify side effects).

**Payload fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `polygon` | `[[lat_deg, lon_deg], ...]` | yes | Tighter than the prior detection's spatial artifact. |
| `confidence` | `float` | yes | `[0, 1]`; mirror of source event's `confidence`. |
| `parent_artifact_id` | `uuid` | yes | The prior detection artifact this footprint refines. |

**CZML template:** `keyhole-footprint`.

**Adjudication flow:** `auto-accept`.

**Time validity:** `start = source_event.ts`; `end =
parent_artifact.time_validity_end` (inherits the parent's expiry).

---

## 5. Non-spatial artifact subtypes

Non-spatial artifacts have no CZML binding (`czml_template_binding IS
NULL`) and do not render on the map. They surface in the EXCON
console's order/report panels (WS-504, WS-505) and feed the AAR
timeline (WS-506).

### 5.1 `order`

Commander → subordinate intent statement.

**Emitted by:**

- `Commander.issue_order` (subtype `directive`).
- `Commander.delegate` (subtype `delegation`).
- `Commander.request_support` (subtype `support_request`).

**Payload fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `order_subtype` | enum `order_subtype` | yes | One of `directive`, `delegation`, `support_request`. |
| `to_entity_id` | `uuid` | conditional | One of `to_entity_id` or `to_echelon` is required. |
| `to_echelon` | enum `echelon` | conditional | |
| `body` | `jsonb` | yes | Subtype-specific. For `directive`: order_type + payload from WS-105.issue_order; for `delegation`: delegated_verbs + ttl_turns; for `support_request`: support_type + payload. |
| `priority` | enum | optional | Mirrors the source event's priority field. |
| `ttl_turns` | `int` | conditional | Required for `delegation`. |

**Adjudication flow:** `auto-accept`. Orders within an entity's chain
of command are routine.

**Time validity:** `start = source_event.ts`; `end = start +
turn_duration * (ttl_turns or 1)`.

### 5.2 `report`

Subordinate → Commander situation update; also produced as a
side-effect of escalation.

**Emitted by:**

- `Communicator.report` (subtype is the source event's `report_type`
  field — `SITREP`, `SPOTREP`, `LOGSTAT`, `CASEVAC`, `INTREP`).
- `Commander.escalate` — emits BOTH an `escalation`-flagged report at
  the source AND a corresponding `report` at the target echelon (per
  WS-105 § Commander.escalate side-effects).

**Payload fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `report_type` | enum `report_type` | yes | `SITREP`, `SPOTREP`, `LOGSTAT`, `CASEVAC`, `INTREP`, or `escalation`. |
| `body` | `jsonb` | yes | Type-specific structured content. |
| `to_echelon` | enum `echelon` | yes | Target echelon. |
| `severity` | enum | conditional | Required when `report_type = escalation`; one of `ROUTINE`, `PRIORITY`, `FLASH`. |
| `references` | `[uuid]` | optional | Event IDs referenced by an escalation. |

**Adjudication flow:** `auto-accept`. `FLASH`-severity escalations also
trigger a banner on the white cell console (WS-505), but acceptance is
not gated on the operator clicking through.

**Time validity:** `start = source_event.ts`; `end = start +
turn_duration` (single-turn shelf life by default).

### 5.3 `comms_traffic`

Message flow on a logical comms channel.

**Emitted by:**

- `Communicator.send` (one artifact per send, with the message routed
  to the recipient's inbox).
- `Communicator.relay` (the message-on-wire of a forwarded send).

**Payload fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `channel` | enum `comms_channel` | yes | |
| `priority` | enum `comms_priority` | yes | `ROUTINE`, `PRIORITY`, `IMMEDIATE`, `FLASH`. |
| `recipient_entity_id` | `uuid` | conditional | One of `recipient_entity_id` or `recipient_role` required. |
| `recipient_role` | `string` | conditional | |
| `message_payload` | `jsonb` | yes | Free-form structured content from the source event. |
| `delivered` | `bool` | yes | Set by adjudicator post-commit. `false` when sender is being jammed in the relevant band at `time_validity_start`. |

**Adjudication flow:** `auto-accept`. Delivery success is decided by
adjudicator inspection of overlapping `jamming_circle` / `ew_cone`
artifacts in the same time window, not by a manual operator decision.

**Time validity:** `start = source_event.ts`; `end = start + 5s`
(comms traffic is a short, transient artifact for AAR replay purposes;
the message itself is a separate logical inbox entry handled by the
agent runtime).

### 5.4 `intel_assessment`

Fusion product produced by an S2 (Sensor-Intelligence) agent. Not
directly emitted by a single officer verb — the S2 agent (WS-403,
WS-404) synthesizes assessments from accumulated sensor artifacts at
between-turn execution.

**Emitted by:**

- The S2 agent in either the blue or red crew, at the end of a
  between-turn cycle. The source event is a synthetic
  `Sensor.classify`-shaped event the agent commits with a
  `czml_template = null` payload field, signaling "this is an
  assessment, not a single observation."

**Payload fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `assessment_kind` | enum `intel_kind` | yes | One of `enemy_disposition`, `enemy_capability`, `friendly_status`, `terrain`, `threat_warning`. |
| `confidence` | `float` | yes | `[0, 1]`. |
| `body` | `jsonb` | yes | Free-form structured content (often a Markdown narrative + a list of references). |
| `references` | `[uuid]` | yes | Sensor artifact IDs the assessment fuses. Non-empty by convention; an assessment with zero references is suspicious and flagged for review. |

**Adjudication flow:** `auto-accept` when `references` is non-empty.
`review` when `references` is empty (catch agent hallucinations).

**Time validity:** `start = source_event.ts`; `end = start +
turn_duration * 2` (assessments age over two turns by default; the
S2 agent re-emits a fresh assessment each turn).

---

## 6. Verb → artifact emission table

The canonical mapping. Every CZML-emitting verb in WS-105 produces
exactly one row in this table, one of the spatial subtypes is bound
to its source event, and a non-spatial artifact may also be emitted.

| Officer | Verb | Spatial artifact | Non-spatial artifact | Conditional notes |
|---|---|---|---|---|
| Sensor | `detect` | depends on modality (see below) | — | Modality-keyed; see [§ 6.1](#61-detect-modality-mapping). |
| Sensor | `track` | continuation of `detect`'s artifact (no new row) | — | Updates parent's `time_validity_end` rather than emitting a new artifact. |
| Sensor | `classify` | `keyhole_footprint` | — | Always; tightens the parent detection's polygon. |
| Sensor | `lose_track` | — | — | Closes the track; sets parent's `time_validity_end = now`. No new artifact. |
| Effector | `engage` | `indirect_fire_arc` (or DIRECT-style equivalent — out of v1 visual scope) | — | Family selected by `weapon_system.delivery_mode`. Emits a follow-on detonation event automatically per WS-105. |
| Effector | `suppress` | `indirect_fire_arc` with `mode=suppress` | — | |
| Effector | `destroy` | `indirect_fire_arc` + `ir_plume` (two artifacts, same source event) | — | Always `always-contested` per [§ 4.6](#46-indirect_fire_arc). |
| Effector | `disable` | depends on `method` | — | `KINETIC` → `indirect_fire_arc` (smaller plume); `EW` → `jamming_circle` or `ew_cone`; `CYBER` → no spatial artifact. |
| Mover | `move_to` | — | — | Mover verbs update entity kinematics, not artifacts. |
| Mover | `follow_route` | — | — | |
| Mover | `halt` | — | — | |
| Mover | `assume_posture` | — | — | |
| Communicator | `send` | — | `comms_traffic` | |
| Communicator | `relay` | `uas_corridor` (conditional — when airborne AND `advertise_corridor=true`) | `comms_traffic` | |
| Communicator | `jam` | `jamming_circle` (omni) or `ew_cone` (directional) | — | Validator picks based on platform aperture profile. |
| Communicator | `report` | — | `report` | Subtype = source event's `report_type`. |
| Commander | `issue_order` | — | `order` (subtype `directive`) | |
| Commander | `request_support` | — | `order` (subtype `support_request`) | |
| Commander | `delegate` | — | `order` (subtype `delegation`) | |
| Commander | `escalate` | — | `report` (subtype `escalation`) AT SOURCE + `report` (regular subtype) AT TARGET ECHELON | Two `report` rows from one source event. |

`intel_assessment` is the one non-verb-emitted artifact; it is
synthesized by the S2 agent during between-turn execution (see [§ 5.4](#54-intel_assessment)).

### 6.1 `detect` modality mapping

| Modality | Spatial artifact | Notes |
|---|---|---|
| `EO_IR` | none in v1 | Optical/IR detection has no canonical CZML shape. Would normally render as a small directional indicator; deferred. Captured as a non-spatial event-only artifact. |
| `RF` | `ew_cone` | Passive ELINT cone of detection. |
| `RADAR` | `radar_fan` | Active radar; coverage volume. |
| `ACOUSTIC` | `masint_cell` | |
| `SEISMIC` | `masint_cell` | |
| `MASINT_MULTI` | `masint_cell` | |

When the owning entity has `type_category = SPACE_UNIT`, the spatial
artifact is upgraded to `satellite_swath` regardless of modality (the
satellite's pass footprint dominates the per-modality shape).

---

## 7. Cross-cutting rules

### 7.1 Multiple artifacts per event

Most events produce one artifact. Three cases produce two:

1. `Effector.destroy` → `indirect_fire_arc` + `ir_plume`. Same
   `source_event_id` on both rows.
2. `Communicator.relay` (when airborne and corridor-advertising) →
   `uas_corridor` + `comms_traffic`. Same source event.
3. `Commander.escalate` → `report` (escalation, at source) + `report`
   (regular, at target echelon). Same source event.

The kernel write path inserts all artifacts atomically in a single
transaction so the `proposed`-state pair is either both present or
neither.

### 7.2 Artifact cascade on adjudication

When a parent artifact transitions to `rejected`, child artifacts (those
with `parent_artifact_id` set, i.e., `keyhole_footprint`) cascade to
`rejected` as well. The cascade is recorded as a separate
`adjudication_history` entry on the child with
`rationale = "parent rejected (id=...)"`.

A `rejected` parent does not retroactively reject prior detections that
fed the parent — only future-emitted children. This is intentional:
the adjudicator may reject a *classification* without invalidating the
underlying *detection*.

### 7.3 Capability profile at emission, not at render

`capability_profile_ref` is captured at emission. If the white cell
edits a profile mid-scenario (which they cannot do per WS-106 § 5
versioning, but in case of a fork), the existing artifacts retain their
original profile reference. The renderer always renders against the
artifact's captured profile, never the entity's current profile.

### 7.4 Time-validity ordering vs adjudication-state ordering

`time_validity_start` and `created_at` are independent. An artifact
emitted at turn N may have `time_validity_start = turn-N+2` (e.g., a
satellite pass scheduled in advance). The override gateway considers
the artifact `proposed` from `created_at` onward, not from
`time_validity_start`; rendering is gated on `accepted` AND
`time_validity_start ≤ now < time_validity_end`.

---

## 8. Open questions

1. **`EO_IR` detect spatial shape.** Currently no spatial artifact is
   emitted. A small directional `radar_fan`-shaped indicator may be
   appropriate; deferred to WS-201 template authoring.
2. **DIRECT-fire arc rendering.** WS-201 will land an `indirect-fire-arc`
   template, but `Effector.engage` with `delivery_mode = DIRECT` (small
   arms, line-of-sight cannon) currently has no template. v1 visual
   scope is indirect-only; direct fire is captured as an event but does
   not render. Decide before WS-201 closes.
3. **`comms_traffic` `delivered` resolution.** Adjudicator-side jam
   detection requires the artifact to be re-evaluated *after* jam
   artifacts in the same window are accepted/rejected. The
   between-turn ordering of these checks is a WS-405 (#25) concern.
4. **Cascade behavior on `accepted` parent → `contested` parent.**
   When a parent artifact moves from `accepted` to `contested` (via
   re-contest), should children automatically re-enter `proposed`?
   v1 says no — children's state is independent — but this needs
   confirmation from WS-405 design.
5. **`intel_assessment` source_event shape.** Using a synthetic
   `Sensor.classify`-shaped event is a workaround. A cleaner long-term
   approach is a 21st verb (`Sensor.fuse` or `Commander.assess`); out
   of v1 vocabulary scope.
6. **Adjudication history retention.** The history is append-only,
   uncapped in v1. For long scenarios with many re-contests this could
   grow unbounded. Compression / archival policy deferred.
7. **`assume_posture` artifact.** Postures change capability gates but
   produce no artifact. A future `posture_change` non-spatial artifact
   might be useful for AAR readability; not required for v1.
8. **Cross-tenant `intel_assessment` sharing.** White cell may want to
   propagate red intel to blue (or vice versa) for training scenarios.
   Out of v1 — every artifact strictly tenant-scoped.

---

## References

- Neutral schema: [`entity-event.md`](entity-event.md) (WS-101).
- Officer interface contracts: [`officer-interfaces.md`](officer-interfaces.md) (WS-105).
- Capability profile schema: [`capability-profiles.md`](capability-profiles.md) (WS-106).
- Glossary — effect families and non-spatial type definitions: [`docs/glossary.md` § 2](../glossary.md#2-effect-families).
- CZML template library (downstream): WS-201 (#13).
- CZML validator (downstream): WS-202 (#14).
- White cell adjudicator agent (downstream): WS-405 (#25).
- AAR replay (downstream): WS-506 (#31).
