# Almighty — Officer interface contracts (v1)

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

This document is the canonical specification for the five officer
interfaces and their 20 action verbs. Every PyRapide event committed by
an agent traces back to one row in this document. The CrewAI tool
wrappers (WS-402) implement one tool per verb; the validator (WS-202)
enforces the parameter ranges declared in the calling agent's capability
profile (WS-106 / WS-107).

The verb vocabulary is locked here. The corresponding `CHECK` constraint
on `events.action_verb` is the planned ALTER TABLE in
[`kernel/schema/events.sql`](../../kernel/schema/events.sql); deferred
until this doc lands and is reviewed.

Cross-references:

- Officer types defined in [`docs/glossary.md` § 1](../glossary.md#1-officer-types).
- Effect families defined in [`docs/glossary.md` § 2](../glossary.md#2-effect-families).
- Event payload column in [`docs/schema/entity-event.md`](entity-event.md).
- Capability profile schema (downstream): WS-106 (#10).
- Effect artifact taxonomy (downstream): WS-108 (#12).

---

## Conventions

- All identifiers are RFC 4122 UUID v4 unless otherwise noted.
- Coordinates are WGS-84: `lat_deg ∈ [-90, 90]`, `lon_deg ∈ [-180, 180]`,
  `alt_m` above the WGS-84 ellipsoid.
- All physical quantities are SI: meters, m/s, radians, seconds, watts,
  kilograms.
- Angles are radians unless field name ends in `_deg`.
- Every verb produces exactly one PyRapide event whose `action_verb` is
  the verb's lowercase name (e.g., `detect`, `engage`, `issue_order`).
  The event's `payload` is the verb's parameter set as a JSON object.
- "Adjudication-flagged" verbs cannot auto-commit when stakes are high —
  they go through the override gateway (WS-303) and the white cell
  adjudicator (WS-405).

---

## Summary

| # | Officer | Verb | Adjudication-flagged | Spatial artifact emitted | Stake notes |
|---|---|---|---|---|---|
| 1 | Sensor | `detect` | No | depends on modality | Routine. |
| 2 | Sensor | `track` | No | none (extends prior detection) | Routine. |
| 3 | Sensor | `classify` | No | `keyhole_footprint` | Routine. |
| 4 | Sensor | `lose_track` | No | none | Routine. |
| 5 | Effector | `engage` | Optional | `indirect_fire_arc` | Adjudicated when target is non-combatant or proximity to civilians. |
| 6 | Effector | `suppress` | No | `indirect_fire_arc` (suppression-flagged) | Routine. |
| 7 | Effector | `destroy` | **Yes** | `indirect_fire_arc` + `ir_plume` | Always high-stakes; `human_required = true`. |
| 8 | Effector | `disable` | Optional | depends on method | Adjudicated for cyber and area-effect EW. |
| 9 | Mover | `move_to` | No | none | Routine. |
| 10 | Mover | `follow_route` | No | none | Routine. |
| 11 | Mover | `halt` | No | none | Routine. |
| 12 | Mover | `assume_posture` | No | none | Routine. |
| 13 | Communicator | `send` | No | none (non-spatial) | Routine. |
| 14 | Communicator | `relay` | No | optional `uas_corridor` | Routine. |
| 15 | Communicator | `jam` | Optional | `jamming_circle` | Adjudicated when overlapping civilian band. |
| 16 | Communicator | `report` | No | none (non-spatial) | Routine. |
| 17 | Commander | `issue_order` | No | none (non-spatial) | Routine. |
| 18 | Commander | `request_support` | No | none (non-spatial) | Routine. |
| 19 | Commander | `delegate` | No | none (non-spatial) | Routine. |
| 20 | Commander | `escalate` | No | none (non-spatial) | Routine, but visible to higher echelon. |

The 20 verbs are the complete vocabulary. The corresponding CHECK is:

```sql
ALTER TABLE events ADD CONSTRAINT events_action_verb_chk
  CHECK (action_verb IN (
    'detect', 'track', 'classify', 'lose_track',
    'engage', 'suppress', 'destroy', 'disable',
    'move_to', 'follow_route', 'halt', 'assume_posture',
    'send', 'relay', 'jam', 'report',
    'issue_order', 'request_support', 'delegate', 'escalate'
  ));
```

This statement is also tracked as a TODO in `kernel/schema/events.sql`
ready to drop in once this doc is approved.

---

## 1. Sensor

A Sensor officer observes the battlespace and emits detection, tracking,
and classification artifacts. Sensors cannot directly affect entities —
their output drives Commander decisions.

### `detect`

Identify a previously unobserved target.

**Signature**

| Param | Type | Required | Units | Notes |
|---|---|---|---|---|
| `target_entity_id` | `uuid` | yes | — | The entity being detected. |
| `modality` | enum `sensor_modality` | yes | — | One of `EO_IR`, `RF`, `RADAR`, `ACOUSTIC`, `SEISMIC`, `MASINT_MULTI`. |
| `confidence` | `float` | yes | `[0, 1]` | Detection confidence at emission. |
| `range_m` | `float` | yes | meters | Distance from sensing entity to target at detection time. |
| `czml_template` | `string` | optional | — | Hint for the live adapter (WS-503). Defaults per modality (e.g., `radar-fan` for `RADAR`). |

**Preconditions**

- Sensing entity has `SENSOR` officer in its capability profile.
- `range_m ≤ profile.sensor.<modality>.max_range_m`.
- Line-of-sight check passes for line-of-sight modalities (`EO_IR`,
  `RADAR`). LOS is producer-asserted in v1; the validator does not
  recompute terrain.
- Sensor not currently saturated (track count < `profile.sensor.max_concurrent_tracks`).

**Emitted event**

`action_verb = "detect"`, `source_officer_type = "SENSOR"`. Payload mirrors
the signature.

**Side effects**

- Emits a sensor artifact per WS-108 — modality determines the family
  (`radar_fan`, `ew_cone`, `masint_cell`, `keyhole_footprint`, etc.).
- Reserves a track slot pending a follow-on `track` call.

**Failure modes**

- *Validator*: capability missing `detect`; `range_m` exceeds modality
  max; `confidence` outside `[0, 1]`; `modality` not in profile's
  enabled set.
- *Runtime*: target entity not in same `(tenant_id, scenario_id)`
  namespace; sensor saturation (max tracks reached).

---

### `track`

Maintain a recurring observation on a previously detected target.

**Signature**

| Param | Type | Required | Units | Notes |
|---|---|---|---|---|
| `target_entity_id` | `uuid` | yes | — | |
| `track_id` | `uuid` | optional | — | Auto-assigned if omitted. Returned in event payload. |
| `update_rate_hz` | `float` | yes | Hz | Cadence of position updates. |
| `lifetime_s` | `float` | optional | seconds | Max age before automatic `lose_track`. Defaults to capability `default_track_lifetime_s`. |

**Preconditions**

- A prior `detect` exists in this `(tenant_id, scenario_id)` against
  `target_entity_id` within `lifetime_s`.
- Sensing entity still has the relevant modality.
- `update_rate_hz ≤ profile.sensor.max_update_rate_hz`.

**Emitted event**

`action_verb = "track"`. Payload includes the resolved `track_id`.

**Side effects**

- Opens (or extends) a track record. The track record is non-spatial; the
  underlying detection's spatial artifact is what shows on the map.

**Failure modes**

- *Validator*: capability missing; `update_rate_hz` exceeds capability;
  no prior `detect` for `target_entity_id`.
- *Runtime*: target entity has been removed from the scenario.

---

### `classify`

Refine a track into a typed classification.

**Signature**

| Param | Type | Required | Units | Notes |
|---|---|---|---|---|
| `track_id` | `uuid` | yes | — | Existing track. |
| `classification_label` | `string` | yes | — | Free-form taxonomy ref (e.g., `notional.air.uas.medium`). |
| `confidence` | `float` | yes | `[0, 1]` | |
| `dwell_s` | `float` | yes | seconds | Time accumulated on target before classifying. |

**Preconditions**

- `track_id` resolves to an open track owned by this entity.
- `dwell_s ≥ profile.sensor.<modality>.min_classify_dwell_s`.

**Emitted event**

`action_verb = "classify"`.

**Side effects**

- Emits a `keyhole_footprint` artifact tightening the prior detection
  shape (per WS-108).
- Updates the track's `classification` field.

**Failure modes**

- *Validator*: insufficient dwell; capability missing; unknown label
  taxonomy reference (warning, not failure, in v1).
- *Runtime*: track closed.

---

### `lose_track`

End an open track.

**Signature**

| Param | Type | Required | Units | Notes |
|---|---|---|---|---|
| `track_id` | `uuid` | yes | — | |
| `reason` | enum `track_loss_reason` | yes | — | One of `OUT_OF_RANGE`, `OCCLUDED`, `JAMMED`, `DECONFLICTED`, `DESTROYED_TARGET`, `OPERATOR_REQUEST`. |

**Preconditions**

- Track is open and owned by this entity.

**Emitted event**

`action_verb = "lose_track"`.

**Side effects**

- Closes the track record. Releases the track slot for re-use.

**Failure modes**

- *Validator*: capability missing.
- *Runtime*: track unknown or owned by a different entity.

---

## 2. Effector

An Effector officer delivers kinetic or non-kinetic effect against a
target. Effector verbs are the primary subject of override review and
white cell adjudication because of their irreversibility.

### `engage`

Apply effect to a target. The general-purpose offensive verb.

**Signature**

| Param | Type | Required | Units | Notes |
|---|---|---|---|---|
| `target_entity_id` | `uuid` | conditional | — | Required unless `target_coordinate` is set. |
| `target_coordinate` | `{lat_deg, lon_deg, alt_m}` | conditional | deg, deg, m | Required unless `target_entity_id` is set. |
| `weapon_system` | `string` | yes | — | Capability profile reference (e.g., `notional.indirect.medium`). |
| `volume_count` | `int` | yes | — | Number of rounds / missiles / pulses. |
| `intent` | enum `engage_intent` | optional | — | `NEUTRALIZE` (default), `SUPPRESS_AND_HOLD`, `MARKER`. |

**Preconditions**

- Capability includes `engage` and the named `weapon_system`.
- `weapon_system.ammo_remaining ≥ volume_count`.
- Distance to target ≤ `weapon_system.effective_range_m`.
- For direct-fire systems: line-of-sight asserted by producer.
- For indirect-fire: ballistic feasibility (max ordinate, time-of-flight)
  within capability bounds.

**Emitted event**

`action_verb = "engage"`. Payload mirrors signature.

**Side effects**

- Emits an `indirect_fire_arc` artifact (or direct-fire equivalent —
  family chosen by `weapon_system.delivery_mode`).
- Decrements ammo: `weapon_system.ammo_remaining -= volume_count`.
- Schedules a follow-on detonation event after `time_of_flight_s` (the
  kernel emits this automatically on commit; it does not require a
  second tool call).

**Failure modes**

- *Validator*: capability missing; insufficient ammo; out of range;
  unknown `weapon_system`.
- *Runtime*: target entity removed mid-flight (the detonation still
  resolves but produces a `miss` follow-on event).
- *Adjudication*: the override gateway flags `engage` events with intent
  `NEUTRALIZE` against `force_affiliation = NEUTRAL` for human review.

---

### `suppress`

Apply effect to deny use of an area or asset without destroying it.

**Signature**

| Param | Type | Required | Units | Notes |
|---|---|---|---|---|
| `target_coordinate` | `{lat_deg, lon_deg, alt_m}` | yes | — | |
| `target_polygon` | `[[lat_deg, lon_deg], ...]` | optional | — | Area suppression. Mutually exclusive with point-target use. |
| `weapon_system` | `string` | yes | — | |
| `duration_s` | `float` | yes | seconds | Suppression dwell. |
| `rate_per_min` | `float` | yes | per minute | Round/pulse cadence. |

**Preconditions**

- Capability includes `suppress` and `weapon_system`.
- Total ammo consumed `(rate_per_min * duration_s / 60) ≤ ammo_remaining`.
- Range as for `engage`.

**Emitted event**

`action_verb = "suppress"`.

**Side effects**

- Emits `indirect_fire_arc` artifact with `mode = "suppression"`.
- Decrements ammo proportionally.
- Affected entities have movement and comms degradation while artifact
  is active (adjudicator decides magnitude per WS-405).

**Failure modes**

- *Validator*: same as `engage`.
- *Adjudication*: large polygons (> capability `max_suppression_area_m2`)
  flagged for human review.

---

### `destroy`

Remove a target from the scenario. Always high-stakes.

**Signature**

| Param | Type | Required | Units | Notes |
|---|---|---|---|---|
| `target_entity_id` | `uuid` | yes | — | |
| `weapon_system` | `string` | yes | — | |
| `volume_count` | `int` | yes | — | |
| `justification` | `string` | yes | — | Free-form rationale captured for AAR. |

**Preconditions**

- Capability includes `destroy` (a flagged subset of `engage` — not all
  weapon systems support it; a 5.56 rifle does not "destroy" a tank).
- Same ammo / range checks as `engage`.
- `justification` is non-empty.

**Emitted event**

`action_verb = "destroy"`. The white cell adjudicator (WS-405) flags
`human_required = true` on the proposed resolution; the gateway holds
the event until a white cell operator clicks through.

**Side effects on adjudication accept**

- Emits `indirect_fire_arc` plus `ir_plume` artifacts.
- Decrements ammo.
- Removes the target entity (transitions its state to `destroyed`; rows
  are not deleted — the entity is retained for AAR).

**Failure modes**

- *Validator*: capability missing; ammo; range; missing justification.
- *Runtime*: target already destroyed.
- *Adjudication*: always blocks until human ack — by design.

---

### `disable`

Render a target non-functional without destroying it. Method-dependent.

**Signature**

| Param | Type | Required | Units | Notes |
|---|---|---|---|---|
| `target_entity_id` | `uuid` | yes | — | |
| `method` | enum `disable_method` | yes | — | `KINETIC`, `EW`, `CYBER`. |
| `weapon_system` | `string` | yes | — | Profile reference. |
| `intensity` | `float` | optional | watts (EW), arbitrary (cyber, kinetic) | |

**Preconditions**

- Capability supports the chosen `method`:
  - `KINETIC`: same as `engage` for the named system.
  - `EW`: requires Communicator-side `jam` capability; this verb borrows it.
  - `CYBER`: requires `cyber_disable` capability (not all profiles have it).

**Emitted event**

`action_verb = "disable"`.

**Side effects**

- `KINETIC`: emits `indirect_fire_arc`; target enters `disabled` state.
- `EW`: emits `jamming_circle`; target's comms are degraded for the
  duration of the artifact.
- `CYBER`: non-spatial only; target enters `disabled` state.
- All methods: target's effective capability is gated to a
  reduced subset until repair (out of scope for v1).

**Failure modes**

- *Validator*: capability missing for chosen method.
- *Adjudication*: `CYBER` and area-effect `EW` flagged for review.

---

## 3. Mover

A Mover officer changes position or posture. Mover verbs do not produce
spatial artifacts directly — movement shows up as entity-state updates
rendered by the live adapter (WS-503).

### `move_to`

Move to a single coordinate.

**Signature**

| Param | Type | Required | Units | Notes |
|---|---|---|---|---|
| `target_lat_deg` | `float` | yes | degrees | |
| `target_lon_deg` | `float` | yes | degrees | |
| `target_alt_m` | `float` | yes | meters | |
| `speed_mps` | `float` | optional | m/s | Default `profile.mover.cruise_speed_mps`. |

**Preconditions**

- Capability includes `move_to`.
- `speed_mps ≤ profile.mover.max_speed_mps`.
- Target reachable (terrain check; v1 trusts producer).

**Emitted event**

`action_verb = "move_to"`.

**Side effects**

- Updates entity kinematics over the move duration. The entity's
  `position_*` and `velocity_*` columns are updated continuously while
  the move is active (adapter detail; not a per-tick event flood).
- No spatial artifact.

**Failure modes**

- *Validator*: speed exceeds capability; target unreachable per
  producer's terrain model.
- *Runtime*: posture change required mid-move (handled by an
  intermediate `assume_posture`).

---

### `follow_route`

Move along a sequence of waypoints.

**Signature**

| Param | Type | Required | Units | Notes |
|---|---|---|---|---|
| `waypoints` | `[{lat_deg, lon_deg, alt_m}, ...]` | yes | — | Length ≥ 1. |
| `speed_mps` | `float` | optional | m/s | |
| `loop` | `bool` | optional | — | Default `false`. |

**Preconditions**

- Capability includes `follow_route` (or `move_to` plus N waypoints —
  capability flag).
- All waypoints reachable.
- Same speed bound as `move_to`.

**Emitted event**

`action_verb = "follow_route"`.

**Side effects**

- Sequential `move_to` semantics through waypoints.

**Failure modes**

- *Validator*: empty waypoints list; speed exceeded.

---

### `halt`

Stop motion immediately.

**Signature**

(no parameters)

**Preconditions**

- Capability includes Mover (essentially universal).

**Emitted event**

`action_verb = "halt"`.

**Side effects**

- Zeroes velocity; preserves orientation.
- Cancels any active `move_to` or `follow_route`.

**Failure modes**

- *Validator*: capability missing (rare; Mover is normally available).

---

### `assume_posture`

Change the entity's tactical posture.

**Signature**

| Param | Type | Required | Units | Notes |
|---|---|---|---|---|
| `posture` | enum `entity_posture` | yes | — | One of `HALTED`, `MOUNTED`, `DISMOUNTED`, `DUG_IN`, `ALERT`, `REST`. |
| `transition_s` | `float` | optional | seconds | Time to complete the transition. Default per posture. |

**Preconditions**

- Capability lists the requested `posture` as an allowed transition from
  the current posture (e.g., a wheeled platform cannot `DUG_IN`).

**Emitted event**

`action_verb = "assume_posture"`.

**Side effects**

- Changes the capability gate for subsequent verbs (e.g., `DISMOUNTED`
  unlocks ATGM tools but disables road-march speed).
- Non-spatial — no artifact.

**Failure modes**

- *Validator*: posture not in capability's allowed transitions.

---

## 4. Communicator

Communicator officers manage messaging, relay, and EW posture.

### `send`

Transmit a message to a recipient.

**Signature**

| Param | Type | Required | Units | Notes |
|---|---|---|---|---|
| `recipient_entity_id` | `uuid` | conditional | — | Required unless `recipient_role` set. |
| `recipient_role` | `string` | conditional | — | E.g., `BATTALION_S3`. Required unless `recipient_entity_id` set. |
| `channel` | enum `comms_channel` | yes | — | `VHF`, `UHF`, `HF`, `SATCOM`, `DATA`. |
| `message_payload` | `object` | yes | — | Free-form structured content. |
| `priority` | enum `comms_priority` | optional | — | `ROUTINE`, `PRIORITY`, `IMMEDIATE`, `FLASH`. Default `ROUTINE`. |

**Preconditions**

- Capability includes `send` and the chosen `channel`.
- Channel not currently disabled by hardware degradation events.

**Emitted event**

`action_verb = "send"`.

**Side effects**

- Emits a non-spatial `comms_traffic` artifact per WS-108.
- Routes the message to the recipient's inbox; if the sender is being
  jammed (verified post-commit by adjudicator), the artifact is flagged
  `delivered = false`.

**Failure modes**

- *Validator*: capability missing; channel unavailable.
- *Runtime*: recipient unknown.

---

### `relay`

Forward a message between two parties via this entity.

**Signature**

| Param | Type | Required | Units | Notes |
|---|---|---|---|---|
| `source_entity_id` | `uuid` | yes | — | |
| `recipient_entity_id` | `uuid` | yes | — | |
| `channel` | enum `comms_channel` | yes | — | |

**Preconditions**

- Capability includes `relay`.
- This entity has line-of-sight or appropriate altitude to both source
  and recipient.

**Emitted event**

`action_verb = "relay"`.

**Side effects**

- Emits a `comms_traffic` artifact.
- If this entity is airborne (UAS / aircraft acting as a relay),
  optionally emits a `uas_corridor` artifact spanning the relay path —
  triggered when `profile.communicator.advertise_corridor = true`.

**Failure modes**

- *Validator*: capability missing.

---

### `jam`

Deny use of an RF band over an area.

**Signature**

| Param | Type | Required | Units | Notes |
|---|---|---|---|---|
| `target_polygon` | `[[lat_deg, lon_deg], ...]` | yes | — | Closed ring; min 3 vertices. |
| `power_w` | `float` | yes | watts | Effective radiated power. |
| `band` | enum `rf_band` | yes | — | `HF`, `VHF`, `UHF`, `L`, `S`, `C`, `X`, `KU`, `KA`. |
| `duration_s` | `float` | yes | seconds | |

**Preconditions**

- Capability includes `jam` for the chosen `band`.
- `power_w ≤ profile.communicator.<band>.max_power_w`.
- Polygon area within capability's max coverage.

**Emitted event**

`action_verb = "jam"`.

**Side effects**

- Emits a `jamming_circle` artifact (the validator may shrink the
  declared polygon to a circle when the platform is single-aperture).
- Consumes power budget for the duration.
- Affected friendly comms inside the polygon are flagged for adjudicator
  review (fratricide check).

**Failure modes**

- *Validator*: capability missing; power exceeds max; band unsupported.
- *Adjudication*: flagged when polygon overlaps a civilian frequency
  band declared in the scenario configuration.

---

### `report`

Submit a structured report to a higher echelon.

**Signature**

| Param | Type | Required | Units | Notes |
|---|---|---|---|---|
| `report_type` | enum `report_type` | yes | — | `SITREP`, `SPOTREP`, `LOGSTAT`, `CASEVAC`, `INTREP`. |
| `report_payload` | `object` | yes | — | Type-specific fields. |
| `to_echelon` | enum `echelon` | yes | — | `COMPANY`, `BATTALION`, `BRIGADE`, `DIVISION`, `WHITE_CELL`. |

**Preconditions**

- Capability includes `report`.
- `to_echelon` is at or above this entity's echelon.

**Emitted event**

`action_verb = "report"`.

**Side effects**

- Emits a non-spatial `report` artifact per WS-108.
- Routes to the target echelon's inbox.

**Failure modes**

- *Validator*: capability missing; `to_echelon` below this entity's echelon.

---

## 5. Commander

Commander officers issue intent, request support, delegate authority,
and escalate. Commander verbs are non-spatial — they produce orders,
requests, and reports rather than direct effects on the battlespace.

### `issue_order`

Direct a subordinate to take action.

**Signature**

| Param | Type | Required | Units | Notes |
|---|---|---|---|---|
| `to_entity_id` | `uuid` | conditional | — | Required unless `to_echelon` set. |
| `to_echelon` | enum `echelon` | conditional | — | Required unless `to_entity_id` set; broadcasts. |
| `order_type` | enum `order_type` | yes | — | `MOVE`, `ATTACK`, `DEFEND`, `RECON`, `SUPPORT`, `WITHDRAW`. |
| `order_payload` | `object` | yes | — | Type-specific (e.g., `MOVE` carries waypoints). |
| `priority` | enum `order_priority` | optional | — | `LOW`, `MEDIUM`, `HIGH`. Default `MEDIUM`. |

**Preconditions**

- This entity has Commander officer.
- Recipient is in this entity's chain of command (validated against the
  capability profile's `subordinates_under` field).

**Emitted event**

`action_verb = "issue_order"`.

**Side effects**

- Emits a non-spatial `order` artifact.
- Recipient's agent (WS-403 / WS-404) receives the order at the start
  of the next between-turn execution window.

**Failure modes**

- *Validator*: not a Commander; recipient outside chain of command.

---

### `request_support`

Ask higher echelon (or a sister unit) for an asset.

**Signature**

| Param | Type | Required | Units | Notes |
|---|---|---|---|---|
| `support_type` | enum `support_type` | yes | — | `FIRES`, `ISR`, `MEDEVAC`, `LOGISTICS`, `EW`, `AIR`. |
| `target_coordinate` | `{lat_deg, lon_deg, alt_m}` | optional | — | Required for `FIRES` / `MEDEVAC`. |
| `justification` | `string` | yes | — | |
| `priority` | enum `request_priority` | yes | — | `LOW`, `MEDIUM`, `HIGH`, `IMMEDIATE`. |

**Preconditions**

- Capability includes `request_support` for the chosen `support_type`.

**Emitted event**

`action_verb = "request_support"`.

**Side effects**

- Emits a non-spatial `request` artifact.
- Routes to the supporting echelon. Fulfillment is a separate event chain
  (the higher commander's `delegate` or `issue_order`).

**Failure modes**

- *Validator*: capability missing; missing required field for
  type-dependent payload.

---

### `delegate`

Hand subordinate authority for a subset of verbs to another entity.

**Signature**

| Param | Type | Required | Units | Notes |
|---|---|---|---|---|
| `to_entity_id` | `uuid` | yes | — | |
| `delegated_verbs` | `[string]` | yes | — | Subset of own verb authority. |
| `ttl_turns` | `int` | yes | turns | Validity window. |

**Preconditions**

- This entity has Commander officer.
- `delegated_verbs ⊆ this_entity.capability.action_verbs_available`.
- Recipient does not already hold a conflicting delegation (revoke
  first if needed).

**Emitted event**

`action_verb = "delegate"`.

**Side effects**

- Emits a non-spatial `delegation` artifact.
- Recipient's effective capability gate is widened by `delegated_verbs`
  for `ttl_turns`.

**Failure modes**

- *Validator*: trying to delegate verbs not in own authority;
  conflicting active delegation.

---

### `escalate`

Push a decision to higher echelon.

**Signature**

| Param | Type | Required | Units | Notes |
|---|---|---|---|---|
| `reason` | `string` | yes | — | Free-form, recorded for AAR. |
| `severity` | enum `escalation_severity` | yes | — | `ROUTINE`, `PRIORITY`, `FLASH`. |
| `to_echelon` | enum `echelon` | yes | — | Strictly higher than this entity's echelon. |
| `references` | `[uuid]` | optional | — | Event IDs being escalated. |

**Preconditions**

- This entity has Commander officer.
- `to_echelon` strictly higher than this entity's echelon.

**Emitted event**

`action_verb = "escalate"`.

**Side effects**

- Emits a non-spatial `escalation` artifact.
- Generates a corresponding `report` artifact at the target echelon.
- `FLASH` severity escalations also pop a banner on the white cell
  console (WS-505).

**Failure modes**

- *Validator*: target echelon not strictly higher.

---

## Validator integration

The CZML validator (WS-202) is the enforcement point for capability
gating on every CZML-emitting verb. The flow per commit:

1. Officer tool (WS-402) is called with the verb's parameter set.
2. The tool checks the calling agent's
   `capability_profile.action_verbs_available` for the verb name.
   On miss, raises immediately — does not call the validator.
3. The tool builds the appropriate CZML packet (if the verb produces
   a spatial artifact) and POSTs it to the validator with the
   capability profile and agent identity.
4. Validator confirms the verb's parameters are inside the profile's
   ranges (e.g., `engage.weapon_system.effective_range_m`,
   `jam.power_w`, `detect.range_m`).
5. On accept, the tool calls `NamespacedDag.commit()` (WS-104) with
   a `KernelEvent` whose `action_verb` is the lowercase verb name.
6. Override gateway (WS-303) intercepts before commit lands; per-event
   policies may flip the path to manual review.

Verbs that do not produce CZML (`move_to`, `assume_posture`, `send`,
`report`, `issue_order`, `request_support`, `delegate`, `escalate`,
`halt`, `lose_track`) skip step 3 — their parameters are still
capability-gated by step 4 (the validator can run on JSON payloads
alone), but no CZML packet is built.

---

## Open questions tracked elsewhere

- **Posture transition matrix** — which postures can transition to which
  others? Tracked under WS-106 (capability profile schema).
- **Track lifetime defaults** — final values per modality belong in
  `kernel/capability-profiles/` (WS-107).
- **Adjudication thresholds** — exact stake-level heuristics for the
  white cell adjudicator are owned by WS-405 (#25); this doc only flags
  which verbs are eligible for review.
- **Order fulfillment chain** — how `request_support` resolves into
  downstream `issue_order` / `delegate` is the agents' responsibility
  (WS-403 / WS-404); the schema only defines the emission shape.

---

## References

- Glossary: [`docs/glossary.md`](../glossary.md)
- Event/entity schema: [`docs/schema/entity-event.md`](entity-event.md)
- Effect artifact taxonomy (downstream): WS-108 (#12)
- Capability profile schema (downstream): WS-106 (#10)
- Capability profile library (downstream): WS-107 (#11)
- Officer interface tools (downstream): WS-402 (#22)
- CZML validator (downstream): WS-202 (#14)
