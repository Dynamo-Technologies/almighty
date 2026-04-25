# Almighty — Glossary

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

This file is the single source of truth for terminology used across the
Almighty platform. Every other doc, issue, and code comment that introduces
a term in scope below MUST link back here rather than re-defining it. If a
term is missing or ambiguous, open a PR against this file before using it
elsewhere.

Linking convention: when the term appears in another document, link to the
anchor (e.g., `[Sensor](glossary.md#sensor)` or
`[per-event override](glossary.md#per-event-scope)`).

---

## 1. Officer types

The five officer interfaces define the entire vocabulary of agent action in
the simulation. Every PyRapide event traces back to one verb on one officer
type. See `docs/schema/officer-interfaces.md` (WS-105) for verb signatures.

### Sensor
An officer that observes the battlespace and emits detection, tracking, and
classification artifacts.
- Verbs: `detect`, `track`, `classify`, `lose_track`.
- Produces sensor artifacts (radar fan, EW cone, MASINT cell, keyhole
  footprint, satellite swath).
- Cannot directly affect entities — sensor output feeds Commander decisions.

### Effector
An officer that delivers kinetic or non-kinetic effect against a target.
- Verbs: `engage`, `suppress`, `destroy`, `disable`.
- Produces effector artifacts (indirect fire arc, jamming circle, IR plume).
- Effector verbs are the primary subject of override review (WS-303) and
  white cell adjudication (WS-405) because of their irreversibility.

### Mover
An officer that changes the position or posture of an entity.
- Verbs: `move_to`, `follow_route`, `halt`, `assume_posture`.
- Produces no spatial artifacts itself; emits position-update events that
  the renderer consumes directly.
- Posture changes (e.g., dismount, dig in) are first-class — they affect
  capability availability per the entity's profile.

### Communicator
An officer that manages messaging, relaying, and the EW posture of an entity.
- Verbs: `send`, `relay`, `jam`, `report`.
- Produces UAS corridor (when `relay` is used as a comms relay) and
  jamming circle artifacts.
- Comms degradation events are the canonical input to S6 (WS-403) decisions.

### Commander
An officer that issues intent, requests support, delegates authority, and
escalates issues to higher echelon.
- Verbs: `issue_order`, `request_support`, `delegate`, `escalate`.
- Produces non-spatial artifacts only (orders, reports).
- Commanders cannot bypass capability profile constraints — an order to
  engage out of effective range is rejected at the validator.

---

## 2. Effect families

Nine spatial effect families plus four non-spatial artifact types. CZML
templates exist per spatial family (WS-201). Each entry below points at the
template name.

### EW cone
Directional electronic-warfare emission, parametrized by azimuth, beamwidth,
and effective range.
- Template: `ew-cone.czml.json`.
- Emitted by: Sensor (passive ELINT), Communicator (active jamming setup).

### UAS corridor
Unmanned aircraft system flight corridor, parametrized as a polyline with
altitude band and time validity.
- Template: `uas-corridor.czml.json`.
- Emitted by: Sensor (ISR overflight), Mover (UAS deployment).

### Radar fan
Radar coverage volume, parametrized by origin, azimuth, sweep arc, and range.
- Template: `radar-fan.czml.json`.
- Emitted by: Sensor (ground or air-based radars).

### Jamming circle
Omnidirectional jamming volume, parametrized by center and effective radius.
- Template: `jamming-circle.czml.json`.
- Emitted by: Communicator (`jam` verb).

### Satellite swath
Transient ground footprint of an overhead pass, parametrized by start/end
coordinates, swath width, and pass duration.
- Template: `satellite-swath.czml.json`.
- Emitted by: Sensor (satellite or high-altitude ISR asset).

### Indirect fire arc
Ballistic trajectory plus impact polygon, parametrized by firing point,
impact point, dispersion ellipse, and time-of-flight.
- Template: `indirect-fire-arc.czml.json`.
- Emitted by: Effector (`engage` verb with indirect-fire capability).

### IR plume
Vertical infrared signature, parametrized by location, peak intensity, and
decay curve.
- Template: `ir-plume.czml.json`.
- Emitted by: Effector (impact aftermath); occasionally Sensor (when an
  IR-only sensor is the source of detection).

### MASINT cell
A bounded measurement-and-signature-intelligence collection cell, parametrized
by polygon, signal type (acoustic, seismic, RF, etc.), and dwell window.
- Template: `masint-cell.czml.json`.
- Emitted by: Sensor (`classify` verb on a MASINT-capable platform).
- **NAMING:** "MASINT" stands for **M**easurement **A**nd **S**ignature
  **INT**elligence. The form **"Mzent"** is a transcription error from the
  planning session and is **NOT** a real term — do not use it anywhere
  in code, comments, docs, or commit messages.

### Keyhole footprint
Refined polygonal footprint produced when overlapping ISR observations
correlate. Tighter than a satellite swath; usually the output of cross-cued
collection.
- Template: `keyhole-footprint.czml.json`.
- Emitted by: Sensor (`classify` verb after fusion).

### Non-spatial artifact types

Four additional artifact categories that do not have CZML bindings:
- **Order** — Commander → subordinate intent statement.
- **Report** — subordinate → Commander situation update.
- **Comms traffic** — message flow on a logical channel; used by EW
  adjudication.
- **Intel assessment** — S2-produced fusion product; references underlying
  sensor artifacts.

---

## 3. Echelons

Echelons define organizational scope for both the entity model and the
agent crews (WS-403, WS-404, WS-405).

### Battalion
The highest echelon modeled in v1. A blue battalion is one tenant's primary
maneuver formation; the OpFor battalion mirrors it on the red side.
- Composition: HQ (S2/S3/S6) + three companies.
- Crew analogue: `agents/blue/` and `agents/red/` each contain one battalion
  crew.

### Company
A subordinate maneuver element under battalion command.
- Composition: company commander + organic combat power (varies by
  capability profile).
- Crew analogue: `co_a.py`, `co_b.py`, `co_c.py` per side.

### OpFor mirror
The structural pattern that requires every blue echelon to have a parallel
red echelon at equivalent scope.
- Purpose: keeps the simulation symmetric so override and adjudication
  policies apply identically to either side.
- Implementation: red crew (WS-404) replicates blue crew (WS-403) but is
  bound to a red capability profile (peer / near-peer / hybrid).

### White cell
The non-combatant adjudicator role that owns turn advancement, override
authoring, capability profile authoring, and contested-effect resolution.
- Composition: human white cell operator(s) + the white cell adjudicator
  agent (WS-405).
- White cell sits OUTSIDE the blue/red structure and has cross-tenant
  visibility within its own tenant scope.

---

## 4. Tiers

Architectural layers. See `docs/architecture.md` and
`docs/diagrams/architecture-v1.svg` (WS-002) for the visual.

### Tier 1 — Renderer
The Resium-based 3D battlespace plus EXCON consoles (WS-504), white cell
console (WS-505), and AAR replay (WS-506).
- Owner: @alexcurnowdynamo.
- Code lives under `web/`.

### Tier 2 — Orchestration
The multi-tenant control plane (WS-301), turn controller (WS-302), override
gateway (WS-303), and WebSocket fan-out (WS-304).
- Owner: @alexcurnowdynamo.
- Code lives under `services/control-plane/` and `services/websocket/`.

### Tier 3 — Agents
CrewAI between-turn execution (WS-401), officer interface tools (WS-402),
and the blue/red/white cell crews (WS-403, WS-404, WS-405).
- Owner: @devindynamo.
- Code lives under `agents/`.

### Tier 4 — Kernel
The PyRapide DAG with tenant/scenario namespacing (WS-104), the neutral
entity/event schema (WS-101), DIS/HLA adapter contracts (WS-102, WS-103),
capability profiles (WS-106, WS-107), and effect artifact taxonomy (WS-108).
- Owner: @shanedynamo (kernel design); @devindynamo (capability profile
  work).
- Code lives under `kernel/` and `services/czml-validator/`,
  `services/czml-adapter/`.

---

## 5. Override scopes

The override gateway (WS-303) intercepts agent-emitted events before they
commit to the DAG. Three scopes are defined; composition order is fixed.

### Per-event scope
A policy bound to a single specific event ID.
- Use when: the white cell wants to make a one-off ruling (e.g., "this
  particular indirect fire mission requires manual approval").
- Highest priority. Always wins if applicable.

### Per-agent-per-turn scope
A policy bound to a (agent_id, turn) pair.
- Use when: the white cell wants to gate or auto-approve everything from
  a specific officer for a single turn (e.g., "auto-block all of red S3's
  effector calls this turn").
- Middle priority.

### Per-turn scope
A policy bound to a single turn covering all events.
- Use when: the white cell wants a blanket rule for a turn (e.g.,
  "auto-approve everything turn 1; manual review starts turn 2").
- Lowest priority.

### Composability rule

When more than one policy applies to an event, the highest-priority scope
wins. Ordering is strict and well-known:

1. **Per-event** beats everything.
2. **Per-agent-per-turn** beats per-turn.
3. **Per-turn** is the floor.

If no policy applies, the gateway default is `review` — the event blocks
until a white cell operator decides. This means an empty policy table is
equivalent to "everything requires manual review", not "everything
auto-commits."

---

## 6. Cross-cutting concepts

Concepts that span multiple tiers.

### Capability profile
An immutable-from-turn-1 description of what an entity (or class of
entities) can do — officer types available, action verbs, parameter ranges,
and (for red profiles) uncertainty bands.
- Schema: WS-106. Templates: WS-107.
- Bound to entities at scenario start. Edits create a new `profile_id`
  rather than mutating in place; this preserves replay correctness.
- The validator (WS-202) enforces the profile on every CZML packet emitted
  via an officer interface tool (WS-402).

### Artifact
The persistent record of an effect or non-spatial output. Every CZML packet
shown to the renderer corresponds to an artifact in the kernel.
- Schema: WS-108.
- Adjudication state machine: `proposed` → `accepted` | `rejected` |
  `contested` → `resolved`.
- Non-spatial artifacts (orders, reports, comms traffic, intel assessments)
  exist outside the CZML pipeline.

### Between-turn execution
The phase in which agents act. Game time is paused; agent crews run
sequentially (blue → red → white adjudicator) inside a tenant-scoped worker.
- Harness: WS-401.
- Each crew run produces a batch of PyRapide events; the override gateway
  filters them before commit.
- Between-turn duration is bounded — if the harness exceeds a configured
  timeout, the turn controller (WS-302) advances anyway with whatever
  events committed.

### Unclassified banner
A mandatory visual surface element on every Tier 1 view and every exported
artifact, including AAR PDFs.
- Format: full-width strip, top AND bottom of the surface, background
  `#C0DD97` (light green), dark text (`#111`), font-size ≤10px.
- Text: exactly `UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY`.
- Reference implementation: `web/renderer/src/components/Banner.tsx`
  (WS-501).
- Banners are also reproduced inside the architecture diagram itself
  (WS-002) so any export of the diagram alone carries the marking.

### Tenant isolation
The hard boundary between tenants. No data, event, or message ever crosses
tenants; every record carries a `tenant_id` and every query is parameterized
on it.
- AWS-side: per-tenant VPC subnet, RDS instance, S3 bucket, KMS key (WS-004).
- Application-side: every JWT carries `tenant_id`; every endpoint
  cross-checks against the URL parameter; every WebSocket fan-out delivery
  is filtered on `tenant_id`.
- Stress-tested at WS-304 (4 concurrent tenants, zero cross-talk required).

---

## Maintenance

- **Adding a term:** open a PR against this file BEFORE introducing the term
  in another doc or in code.
- **Renaming a term:** create a new entry, mark the old entry as
  `**Deprecated:**` with a pointer to the new one, leave for one phase, then
  remove.
- **Disagreement on definition:** the issue body wins over this file when
  in conflict. If a term's definition needs to change, update the upstream
  issue first, then sync this file in a follow-up PR.

Last updated: WS-003 (#3).
