# Almighty — HLA FOM adapter contract (v1)

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

This document specifies the translation contract from the neutral entity /
event schema in [`entity-event.md`](entity-event.md) (WS-101) to High-Level
Architecture (HLA) Federation Object Model (FOM) shapes. It is the sibling
of the DIS adapter contract in [`dis-adapter.md`](dis-adapter.md) (WS-102);
where the two share a concern, this doc cross-links rather than duplicating.

**No implementation is in scope here.** This is a contract authored ahead
of the adapter service.

References to HLA cite IEEE Std 1516-2010 (HLA Evolved) section numbers
and SISO-STD-001-2015 (RPR-FOM 2.0) sections. The standards' text is not
reproduced; public references are linked in [§ References](#references).

---

## 1. FOM choice

**Decision: RPR-FOM 2.0 (SISO-STD-001-2015) is the v1 FOM.** No custom
FOM module is added in v1.

### 1.1 Rationale

- RPR-FOM 2.0 is the SISO-standardized FOM derived from DIS, which means
  every concept already mapped in [`dis-adapter.md`](dis-adapter.md) has a
  direct RPR-FOM analogue. Authoring a custom FOM would force a redundant
  semantic design pass when one already exists.
- RPR-FOM is the de-facto interchange FOM for unclassified joint
  exercises; using it maximizes the chance that a third-party federate
  (e.g., a partner's CGF) can join the federation without bespoke gateway
  work.
- The neutral schema's nine effect families and 20 officer verbs all fit
  inside the RPR-FOM 2.0 object / interaction taxonomy with the same
  lossy edges as DIS — see [§ 5](#5-lossy-mappings).

### 1.2 v1 vs RPR-FOM 2.0 delta

There is **no** deviation from RPR-FOM 2.0 in v1. The following extension
points are noted for v2 candidacy but explicitly excluded now:

- A custom interaction class for `lose_track` (no native RPR-FOM
  equivalent; same problem as DIS — see [§ 5.1](#51-lose_track-not-representable)).
- Custom attributes for `assume_posture` semantics that don't fit
  Appearance bits.
- A Commander-intent interaction class for `issue_order` / `request_support`
  / `delegate` / `escalate` (currently all collapse to
  `ApplicationSpecificRadioSignal`).

If any of these become hard requirements in v2, the right path is a FOM
module appended to RPR-FOM 2.0, not a wholesale custom FOM.

---

## 2. Scope

### 2.1 RPR-FOM object classes in scope

The kernel publishes object instances rooted at `BaseEntity.PhysicalEntity`
plus radio-emitter object classes under `EmbeddedSystem`.

| RPR-FOM object class (full path) | Maps to neutral `type_category` | Publish / Subscribe |
|---|---|---|
| `BaseEntity.PhysicalEntity.Platform.GroundVehicle` | `PLATFORM` (ground), `GROUND_UNIT` (when motorized) | publish |
| `BaseEntity.PhysicalEntity.Platform.Aircraft` | `AIR_UNIT`, `PLATFORM` (rotary / fixed-wing) | publish |
| `BaseEntity.PhysicalEntity.Platform.SurfaceVessel` | `MARITIME_UNIT` (surface) | publish |
| `BaseEntity.PhysicalEntity.Platform.SubmersibleVessel` | `MARITIME_UNIT` (sub-surface) | publish |
| `BaseEntity.PhysicalEntity.Platform.SpacePlatform` | `SPACE_UNIT` | publish |
| `BaseEntity.PhysicalEntity.Lifeform.Human` | `GROUND_UNIT` (dismounted) | publish |
| `EmbeddedSystem.RadioTransmitter` | (derived from entities with active comms / jam) | publish |
| `EmbeddedSystem.RadioReceiver` | (derived from entities with active sensors) | publish |
| `BaseEntity.PhysicalEntity.Platform.MultiDomainPlatform` | `NON_KINETIC` emitters that carry multiple radio systems | publish |

Inbound (subscribed) classes are the same set; the kernel receives
attribute updates from federate-supplied entities and projects them back
into the neutral schema. **v1 does not transfer ownership** of objects in
either direction (no `requestAttributeOwnershipDivestiture` use); each
entity is owned end-to-end by exactly one federate.

### 2.2 RPR-FOM interaction classes in scope

| RPR-FOM interaction class | Officer verb(s) | Publish / Subscribe |
|---|---|---|
| `WeaponFire` | `Effector.engage` / `suppress` / `destroy` / `disable` | publish |
| `MunitionDetonation` | follow-on event, same verbs as `WeaponFire` | publish |
| `RadioSignal.EncodedAudioRadioSignal` | `Communicator.send` (voice traffic) | publish |
| `RadioSignal.RawBinaryRadioSignal` | `Communicator.relay` (data link payload) | publish |
| `RadioSignal.ApplicationSpecificRadioSignal` | `Communicator.report`, all `Commander.*` verbs | publish |

### 2.3 Out of scope for v1

| RPR-FOM class | Excluded because |
|---|---|
| `Collision` interaction | Same as DIS — v1 does not model contact mechanics. |
| `Munition` object class (persistent in-flight munitions) | Munitions are modeled as `WeaponFire` → `MunitionDetonation` interactions only; no in-flight object representation. |
| `Sensor` object class (RPR-FOM 2.0 sensor declarations) | Sensor capability is captured via `RadioReceiver` objects + capability profiles; the dedicated `Sensor` class is deferred. |
| `Supplies` / `CulturalFeature` / `Expendables` | No logistics or cultural-feature modeling in v1. |
| `EmitterBeam` / `EmitterSystem` | Detailed EW emission patterns deferred; v1 abstracts to `RadioTransmitter` only. |
| `Designator` interaction | Laser designation below v1 fidelity. |
| `IFF` interaction class | Same as DIS — `force_affiliation` covers v1 needs. |
| All federation-management interactions (`StartResume`, `StopFreeze`, `AttributeOwnership*`) | Federation management is handled by the control plane (WS-301), not modeled inside the FOM data path. |

If a federate publishes an out-of-scope class to the federation, the
adapter logs and discards. Same posture as the DIS adapter.

### 2.4 Federation / federate identifiers

The neutral namespace `(tenant_id, scenario_id)` projects to HLA as follows:

| HLA concept | Neutral source | Translation rule |
|---|---|---|
| Federation execution name | `(tenant_id, scenario_id)` | `almighty.<tenant_id>.<scenario_id>` (lowercased UUIDs, no braces). One federation execution per scenario. |
| Federate name | adapter-instance label | `almighty-kernel-<tenant_id>-<adapter_ordinal>`. Single-process v1: ordinal is fixed at `0`. |
| `ObjectInstanceHandle` | `entity_id` | Adapter maintains an `entity_id ↔ ObjectInstanceHandle` table per federation. |
| `InteractionClassHandle` | (constant per class) | Resolved once at federate join. |

The federation execution is created by the control plane at scenario
start (per WS-302) and destroyed at scenario teardown. Cross-tenant
federation membership is impossible by construction: tenant A's
federation execution name embeds tenant A's UUID; an RTI cannot map a
federate from one execution into another.

---

## 3. Conventions

### 3.1 Coordinate systems

RPR-FOM uses ECEF for `WorldLocation` (`meters`) and an Euler-angle
`Orientation` record (psi, theta, phi in radians). Conversion rules are
identical to DIS — see [`dis-adapter.md` § 2.1](dis-adapter.md#21-coordinate-systems).
The same quaternion → Euler drift caveat applies (see
[§ 5.4](#54-orientation-conversion-drift)).

### 3.2 Time

HLA Evolved supports two time-management policies: timestep-regulating /
timestep-constrained federates use `LogicalTime` (HLA-managed); receive-order
federates use wall-clock. The adapter:

- Uses **timestep-regulating + timestep-constrained** for the kernel
  federate. The control plane drives turn advancement (WS-302); each turn
  advances the federation `LogicalTime` by a configurable scenario
  parameter (default: 1 second of sim time per turn).
- Maps neutral `event.ts` to the federation `LogicalTime` value at which
  the interaction or attribute update is sent.
- Within a turn, multiple events may share a `LogicalTime` value; the RTI
  is configured for `event-receive` ordering rather than total time
  ordering, so causal predecessors hold per the neutral schema's
  application-level enforcement.

### 3.3 Force affiliation

Force affiliation maps to RPR-FOM `ForceIdentifierEnum8`:

| Neutral | RPR-FOM `ForceIdentifierEnum8` | Notes |
|---|---|---|
| `BLUE` | `Friendly` (1) | |
| `RED` | `Opposing` (2) | |
| `NEUTRAL` | `Neutral` (3) | |
| `WHITE` | `Other` (0) | Same lossy round-trip as DIS — see [`dis-adapter.md` § 2.3](dis-adapter.md#23-force--affiliation). HLA inherits the same problem; mitigation is shared (out-of-band metadata). Open Question #5 in DIS is the same Open Question here. |

### 3.4 Entity type

RPR-FOM uses an `EntityTypeStruct` record with seven fields (`EntityKind`,
`Domain`, `CountryCode`, `Category`, `Subcategory`, `Specific`, `Extra`)
— byte-for-byte the same as DIS Entity Type. The lookup table is
**shared** between adapters: the same `kernel/schema/dis-entity-types.json`
that resolves DIS Entity Type also feeds HLA `EntityTypeStruct`. This is
the one piece of authoring savings RPR-FOM gives us over a fresh FOM.

---

## 4. Object class field mapping

### 4.1 `BaseEntity.PhysicalEntity` (and all subclass attributes)

Every published platform/lifeform shares the `BaseEntity.PhysicalEntity`
inherited attributes. The mapping covers all of them in one table.

| Neutral field | RPR-FOM attribute | Class on which attribute is published | Notes |
|---|---|---|---|
| `entity_id` | (used as `ObjectInstanceName`, registered at instance discovery) | all | Translation table per [§ 2.4](#24-federation--federate-identifiers). |
| `type_category` + `type_subtype_ref` | `EntityType` | `BaseEntity` | `EntityTypeStruct`; same lookup table as DIS. |
| `position_ecef_x_m / y_m / z_m` | `WorldLocation` | `BaseEntity` | `WorldLocationStruct` (X, Y, Z in meters, ECEF). Direct copy. |
| `velocity_ecef_vx_mps / vy_mps / vz_mps` | `VelocityVector` | `BaseEntity` | `VelocityVectorStruct` (X, Y, Z in m/s, ECEF). Direct copy. |
| `orientation_qw / qx / qy / qz` | `Orientation` | `BaseEntity` | `OrientationStruct` (psi, theta, phi in radians). Quaternion → Euler conversion. |
| `force_affiliation` | `ForceIdentifier` | `PhysicalEntity` | Per [§ 3.3](#33-force-affiliation). |
| `display_name` | `Marking` | `PhysicalEntity` | `MarkingStruct` — 11 ASCII chars + character set byte. Truncation rule identical to DIS. |
| (derived from capability profile, WS-106) | `Capabilities` | `PhysicalEntity` | `CapabilitiesRecord` bitfield. v1 maps a small subset; rest zero. |
| (constant) | `DeadReckoningAlgorithm` | `BaseEntity` | Default `2` (DRM_F_P_W). Same per-category open question as DIS. |
| (constant in v1) | `ArticulatedParametersArray` | `PhysicalEntity` | Empty — no turret modeling. |
| (none — see § 4.2) | `IsConcealed`, `IsFrozen`, etc. (Appearance bits) | per subclass | Per-subclass appearance bits map from selected `assume_posture` payloads where representable. Lossy — see [§ 5.2](#52-assume_posture-loses-semantic). |

### 4.2 Per-subclass attributes

For each subclass listed in [§ 2.1](#21-rpr-fom-object-classes-in-scope),
the subclass-specific attributes (e.g., `Aircraft.AfterburnerOn`,
`GroundVehicle.HullHeading`) are **not populated** in v1. The kernel
publishes only the inherited `BaseEntity` and `PhysicalEntity` attributes
on each subclass instance. Federates that subscribe to subclass-specific
attributes will see them as never-updated; this is acceptable for v1
because RPR-FOM does not require all subscribed attributes to be
published. Tracked as a non-blocking note for v2.

### 4.3 `EmbeddedSystem.RadioTransmitter`

Published when an entity has an active emitter (jam, active radar, voice
comms transmitting). One transmitter object instance per logical radio.

| Neutral source | RPR-FOM attribute | Notes |
|---|---|---|
| `source_entity_id` | `EntityIdentifier` | Owning entity (translates through entity ID table). |
| `payload.radio_id` | `RadioIndex` | 1-indexed logical radio on the platform. |
| `payload.transmit_state` | `TransmitterOperationalStatus` | `0=off`, `1=on-not-transmitting`, `2=on-transmitting`. |
| `payload.frequency_hz` | `Frequency` | Hz. |
| `payload.bandwidth_hz` | `FrequencyBandwidth` | |
| `payload.power_dbm` | `RFPower` | dBm. |
| `payload.modulation` | `MajorModulation`, `Detail`, `System` | RPR-FOM `MajorModulationTypeEnum16` + detail records. |
| `payload.antenna_pattern` | `AntennaPatternData` | v1: omnidirectional only. |

### 4.4 `EmbeddedSystem.RadioReceiver`

Published when an entity has an active receiver (sensor `detect` /
`track` / `classify`).

| Neutral source | RPR-FOM attribute | Notes |
|---|---|---|
| `source_entity_id` | `EntityIdentifier` | Owning entity. |
| `payload.radio_id` | `RadioIndex` | |
| `payload.received_power_dbm` | `ReceivedPower` | dBm. |
| `payload.transmitter_entity_id` | `TransmitterObjectIdentifier` | Cross-reference to the detected emitter. |
| `payload.transmitter_radio_id` | `TransmitterRadioIndex` | |
| `payload.receiver_state` | `ReceiverOperationalStatus` | `0=off`, `1=on-not-receiving`, `2=on-receiving`. |
| `payload.classification` (verb=`classify` only) | (no native attribute) | Classification verdict rides as application-level data inside an `ApplicationSpecificRadioSignal` interaction emitted in tandem with the receiver state update. **Lossy** — see [§ 5.6](#56-classification-verdict-lossy). |

---

## 5. Interaction class field mapping

### 5.1 Verb-to-interaction summary

| Officer | Verb | Interaction(s) | Notes |
|---|---|---|---|
| EFFECTOR | `engage` | `WeaponFire` (+ later `MunitionDetonation`) | Symmetric with DIS. |
| EFFECTOR | `suppress` | `WeaponFire` (`FireMissionIndex` set, `FuseType` = burst) | Suppression via burst fuse. |
| EFFECTOR | `destroy` | `WeaponFire` + `MunitionDetonation` | `DetonationResultCode` carries kill type. |
| EFFECTOR | `disable` | `WeaponFire` + `MunitionDetonation` | Mobility / firepower kill via result code. |
| COMMUNICATOR | `send` | `RadioSignal.EncodedAudioRadioSignal` | Encoded voice. |
| COMMUNICATOR | `relay` | `RadioSignal.RawBinaryRadioSignal` | Data link relay. |
| COMMUNICATOR | `report` | `RadioSignal.ApplicationSpecificRadioSignal` | Application-level data with report header. |
| COMMUNICATOR | `jam` | (no interaction — `RadioTransmitter` object update only) | Persistent emitter state — see [§ 4.3](#43-embeddedsystemradiotransmitter). |
| SENSOR | `detect` | (no interaction — `RadioReceiver` object update only) | Persistent receiver state — see [§ 4.4](#44-embeddedsystemradioreceiver). |
| SENSOR | `track` | (no interaction — `RadioReceiver` periodic update) | |
| SENSOR | `classify` | `RadioSignal.ApplicationSpecificRadioSignal` (with classification header) | Verb is observable only via the application-level header byte. |
| SENSOR | `lose_track` | (none) | **Lossy** — see [§ 5.1](#51-lose_track-not-representable) below. |
| MOVER | `move_to` / `follow_route` / `halt` / `assume_posture` | (no interaction — object attribute updates) | All movement is attribute-update on the entity object. |
| COMMANDER | `issue_order` / `request_support` / `delegate` / `escalate` | `RadioSignal.ApplicationSpecificRadioSignal` | Verb identity in application-level header only. **Lossy** — see [§ 5.3](#53-commander-verbs-collapse-to-applicationspecificradiosignal). |

### 5.2 `WeaponFire` parameters

| Neutral source | RPR-FOM parameter | Notes |
|---|---|---|
| `event_id` | `EventIdentifier` | `EventIdentifierStruct` (issuing object reference + event count). |
| `source_entity_id` | `FiringObjectIdentifier` | Translated through entity ID table. |
| `payload.target_entity_id` | `TargetObjectIdentifier` | When target is an area, set to `RTIobjectIdNotSpecified`. |
| `payload.munition_type_ref` | `MunitionType` | Same lookup table as DIS Munition Type. |
| `payload.burst_count` (default 1) | `FireMissionIndex` (when >1) and `Quantity` | Suppression encoded via burst quantity. |
| `payload.range_m` | `Range` | Meters. |
| `payload.impact_*` | `FiringLocation` (firer's WorldLocation at fire time), `MunitionType.Specific` | RPR-FOM does not carry impact location on `WeaponFire`; impact is on `MunitionDetonation`. |
| `ts` | (federation `LogicalTime` at send) | Per [§ 3.2](#32-time). |

### 5.3 `MunitionDetonation` parameters

| Neutral source | RPR-FOM parameter | Notes |
|---|---|---|
| `event_id` of originating `WeaponFire` | `EventIdentifier` | Same identifier — round is the same simulation event. |
| `payload.firing_entity_id` | `FiringObjectIdentifier` | Carried forward. |
| `payload.target_entity_id` | `TargetObjectIdentifier` | `RTIobjectIdNotSpecified` for area effects. |
| `payload.impact_*` | `DetonationLocation` | ECEF. |
| `payload.detonation_result` | `DetonationResultCode` | Mapped from neutral result enum to RPR-FOM `DetonationResultCodeEnum8`. |
| `payload.relative_detonation_location` | `RelativeDetonationLocation` | Offset from target; v1 default zero. |

### 5.4 `RadioSignal.*` interaction parameters

All three subclasses share the same base parameter set; differences are
in the `EncodingClass` field and which subclass carries the application
payload.

| Neutral source | RPR-FOM parameter | Notes |
|---|---|---|
| `source_entity_id` | `HostObjectIdentifier` | The emitting entity. |
| `payload.radio_id` | `HostRadioIndex` | Logical radio on the platform. |
| `payload.encoding_class` | `EncodingClass` | `EncodedVoice` (1), `RawBinaryData` (2), `ApplicationSpecificData` (3) — picks the subclass. |
| `payload.tdl_type` | `TDLType` | `0` unless Link 16 modeling (out of v1 scope). |
| `payload.sample_rate` | `SampleRate` | `0` for application-specific. |
| `payload.data` | `DataLength`, `DataRate`, `SignalDataLength`, `SignalData` | Application payload as octet array. Commander verbs prepend a 4-byte verb header (same as DIS). |

---

## 5. Lossy mappings

### 5.1 `lose_track` not representable

RPR-FOM 2.0 has no canonical "track lost" interaction or attribute. Same
problem as DIS. The kernel models it as cessation of `RadioReceiver`
attribute updates (or transition of `ReceiverOperationalStatus` from
`on-receiving` to `on-not-receiving`). A federate that observes only
attribute updates cannot distinguish a lost track from a stalled federate.

Mitigation candidate (deferred): a custom FOM-module interaction class
`Almighty.TrackLost` with `(tracker_object_id, tracked_object_id)`
parameters. Open Question #4.

### 5.2 `assume_posture` loses semantic

RPR-FOM `PhysicalEntity` exposes a small set of Appearance bits that map
to a subset of postures (e.g., `Hatch` open/closed, `LightsState`,
`Smoking`). Postures outside this set (`dig_in`, `assume_overwatch`,
`dismount`) are dropped on the wire and visible only to consumers reading
the kernel directly. Same edge as DIS [`§ 5.2`](dis-adapter.md#52-assume_posture-loses-semantic).

### 5.3 Commander verbs collapse to `ApplicationSpecificRadioSignal`

`issue_order`, `request_support`, `delegate`, `escalate` all become
`ApplicationSpecificRadioSignal` interactions with the same
`EncodingClass`. Verb identity rides only in the first 4 bytes of
`SignalData`. A federate that strips the header sees four indistinguishable
command messages.

### 5.4 Orientation conversion drift

Quaternion → Euler → quaternion round-trip drift is identical to DIS
([`§ 5.4`](dis-adapter.md#54-orientation-conversion-drift)). Acceptable
for v1.

### 5.5 WHITE force round-trip

`WHITE → Other (0) → ?` — identical lossy edge to DIS. Cross-linked from
[§ 3.3](#33-force-affiliation). Open Question #5 (DIS) is the same
question here.

### 5.6 Classification verdict lossy

`Sensor.classify`'s output (classification verdict + confidence) does not
fit any RPR-FOM 2.0 receiver attribute. The verdict rides as
application-level data inside an `ApplicationSpecificRadioSignal`
interaction emitted alongside the receiver state update. Federates that
subscribe to receivers but not to ApplicationSpecificRadioSignal lose the
classification.

### 5.7 Subclass attributes dropped

Subclass-specific attributes (e.g., `Aircraft.AfterburnerOn`,
`GroundVehicle.HullHeading`) are never populated by the kernel — see
[§ 4.2](#42-per-subclass-attributes). Federates that depend on these
attributes will see stale or default values.

---

## 6. Open questions

1. **Munition type and entity type lookup tables** — shared with DIS
   adapter (Open Questions #1 and #2 in [`dis-adapter.md`](dis-adapter.md#6-open-questions)).
   Both adapters consume the same JSON. Authoring is a single follow-up
   issue, not two.
2. **Dead-reckoning algorithm per category** — shared with DIS
   ([`dis-adapter.md` Open Question #3](dis-adapter.md#6-open-questions)).
   RPR-FOM uses the same `DeadReckoningAlgorithm` enumeration as DIS.
3. **Time policy choice** — `timestep-regulating + timestep-constrained`
   is the v1 default (see [§ 3.2](#32-time)). If a partner federate uses
   `receive-order` only, the federation degrades to wall-clock. Decide
   whether to enforce the time policy on join or accept degradation.
4. **`lose_track` representation** — shared with DIS
   ([`dis-adapter.md` Open Question #4](dis-adapter.md#6-open-questions)).
   The HLA mitigation (custom FOM-module interaction) is cleaner than the
   DIS mitigation (custom Signal PDU header). If a custom interaction is
   added, both adapters benefit; track jointly.
5. **WHITE force affiliation** — same as
   [`dis-adapter.md` Open Question #5](dis-adapter.md#6-open-questions).
6. **Subclass-attribute publication policy** — v1 publishes only inherited
   `BaseEntity` / `PhysicalEntity` attributes. Decide before any joint
   federation with a partner that subscribes to subclass attributes
   (e.g., an Aircraft federate that wants `AfterburnerOn`).
7. **Object instance ↔ UUID persistence** — shared with DIS
   ([`dis-adapter.md` Open Question #7](dis-adapter.md#6-open-questions)).
   The HLA `ObjectInstanceHandle` is RTI-allocated and only valid inside
   one federation execution; the durable mapping is `UUID ↔
   ObjectInstanceName`, where the name is adapter-controlled. v1 makes
   `ObjectInstanceName` equal to the lower-case UUID string and
   round-trips through that.
8. **RTI vendor** — Pitch pRTI vs MAK RTI vs CertiHLA (open-source) —
   not a contract concern but a deployment one. Tracked under WS-301 /
   WS-004 and explicitly NOT decided here.

---

## 7. Round-trip expectations

Same posture as DIS: in-scope neutral fields MUST round-trip losslessly
modulo [§ 5](#5-lossy-mappings). The regression suite at adapter
implementation time should generate a synthetic neutral row, project to
HLA, project back, and assert structural equality on non-lossy fields.

Note that HLA round-trip is more involved than DIS because the kernel
must (a) register an object instance, (b) update attributes, (c) reflect
attribute updates back, and (d) handle the case where the federation
execution is destroyed and recreated (object handles change; instance
names must persist).

---

## 8. References

- IEEE Std 1516-2010 (HLA Evolved): <https://standards.ieee.org/ieee/1516/4204/>.
- SISO-STD-001-2015 (RPR-FOM 2.0):
  <https://www.sisostandards.org/page/StandardsProductsRprFom>.
- Public RPR-FOM 2.0 reference (SISO digital library; class hierarchy
  diagrams): <https://www.sisostandards.org/page/DigitalLibraryProductRPR-FOM>.
- Pitch pRTI (commercial): <https://pitchtechnologies.com/prti/>.
- CertiHLA (open-source RTI): <https://savannah.nongnu.org/projects/certi>.
- Neutral schema: [`docs/schema/entity-event.md`](entity-event.md) (WS-101).
- DIS adapter contract (sibling): [`docs/schema/dis-adapter.md`](dis-adapter.md) (WS-102).
- Glossary — officer types and verb assignments:
  [`docs/glossary.md#1-officer-types`](../glossary.md#1-officer-types).
