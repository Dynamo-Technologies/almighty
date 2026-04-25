# Almighty — Dummy Instructions

A per-issue execution guide for `Dynamo-Technologies/almighty`. Each entry
contains a Claude Code prompt the assignee can paste into a session opened in
the repo root, plus an explicit step list, files to touch, and the DoD
checklist taken from the issue body.

> **Convention used in every prompt:**
>
> - Open Claude Code in a clone of `git@github.com:Dynamo-Technologies/almighty.git`.
> - Branch off `main` as `ws-NNN/<short-slug>` before any edits.
> - Open the linked GitHub issue in your browser to keep the DoD visible.
> - Every UI surface and any artifact intended for a stakeholder must carry the banner string: `UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY`.
> - Reference `docs/glossary.md` (WS-003) for terminology — do not reinvent terms.

---

## Issue map

| Issue | WS | Title | Assignee | Phase |
|---|---|---|---|---|
| #1 | WS-001 | Repository bootstrap and conventions | @shanedynamo | Phase 0 |
| #2 | WS-002 | Architecture diagram artifact | @shanedynamo | Phase 0 |
| #3 | WS-003 | Glossary and terminology lock | @shanedynamo | Phase 0 |
| #4 | WS-004 | Per-tenant AWS isolation IaC scaffold | @alexcurnowdynamo | Phase 0 |
| #5 | WS-101 | Neutral entity/event schema | @shanedynamo | Phase 1 |
| #6 | WS-102 | DIS PDU adapter contract | @devindynamo | Phase 1 |
| #7 | WS-103 | HLA FOM adapter contract | @devindynamo | Phase 1 |
| #8 | WS-104 | PyRapide DAG tenant/scenario namespacing | @shanedynamo | Phase 1 |
| #9 | WS-105 | Officer interface contracts | @shanedynamo | Phase 1 |
| #10 | WS-106 | Capability profile schema | @devindynamo | Phase 1 |
| #11 | WS-107 | Capability profile library | @shanedynamo | Phase 1 |
| #12 | WS-108 | Effect artifact taxonomy | @devindynamo | Phase 1 |
| #13 | WS-201 | CZML template library — base structures | @alexcurnowdynamo | Phase 2 |
| #14 | WS-202 | Capability-gated CZML validator | @devindynamo | Phase 2 |
| #15 | WS-203 | Static CZML effect catalog (Nashville) | @alexcurnowdynamo | Phase 2 |
| #16 | WS-204 | Static CZML Nashville mini vignette | @alexcurnowdynamo | Phase 2 |
| #17 | WS-301 | Tenant registry and RBAC service | @alexcurnowdynamo | Phase 3 |
| #18 | WS-302 | Turn controller (white cell only) | @alexcurnowdynamo | Phase 3 |
| #19 | WS-303 | Override gateway and policy plane | @alexcurnowdynamo | Phase 3 |
| #20 | WS-304 | WebSocket fan-out service | @alexcurnowdynamo | Phase 3 |
| #21 | WS-401 | Between-turn agent execution harness | @devindynamo | Phase 4 |
| #22 | WS-402 | Officer interface tools | @devindynamo | Phase 4 |
| #23 | WS-403 | Blue battalion crew stubs | @devindynamo | Phase 4 |
| #24 | WS-404 | Red OpFor crew stubs | @devindynamo | Phase 4 |
| #25 | WS-405 | White cell adjudicator agent | @devindynamo | Phase 4 |
| #26 | WS-501 | Resium scaffold | @alexcurnowdynamo | Phase 5 |
| #27 | WS-502 | Static CZML loader | @alexcurnowdynamo | Phase 5 |
| #28 | WS-503 | Live PyRapide CZML adapter | @devindynamo | Phase 5 |
| #29 | WS-504 | EXCON consoles (blue, red) | @alexcurnowdynamo | Phase 5 |
| #30 | WS-505 | White cell console | @alexcurnowdynamo | Phase 5 |
| #31 | WS-506 | AAR replay | @alexcurnowdynamo | Phase 5 |
| #32 | WS-601 | Nashville Cumberland River crossing scenario | @shanedynamo | Phase 6 |

Day-1 ready: **WS-001 (#1)**. Once #1 closes, WS-002/003/004/501 unblock simultaneously.

---

# Phase 0 — Foundations

## WS-001 — Repository bootstrap and conventions

**Issue:** #1 · **Assignee:** @shanedynamo · **Status:** READY (no upstream) · **Parallel-safe with:** #2, #3

> Most of the bootstrap was done by `05-commit-scaffold.sh`. This issue is now mostly *verification + branch protection + project board column wiring*.

### Claude Code prompt

```
You are completing WS-001 (issue #1) in Dynamo-Technologies/almighty.

Most scaffolding has already landed via the planning runbook (initial commit
d90db62 on main). Verify the following are present and correct, and fill any
gaps:

1. Top-level directories: docs/, infra/, services/, web/, agents/, kernel/, czml/.
2. .github/CODEOWNERS, .github/pull_request_template.md, .gitignore, README.md.
3. README references docs/architecture.md (file may not exist yet — that is WS-002).
4. Configure branch protection on main via `gh api`:
   - Require PR before merge
   - Require CODEOWNERS review
   - Require status checks to pass (none defined yet — leave list empty but enable)
   - Block force-push and deletions
5. Verify all 18 custom labels exist (`gh label list --repo Dynamo-Technologies/almighty`).
6. Verify the "Almighty Build" project (number 2) has all 32 issues as items.
7. Configure the project board's Status column with these options if not already
   present: Backlog → Ready → In Progress → Review → Done. Use `gh project
   field-list 2 --owner Dynamo-Technologies` to inspect, then
   `gh project field-edit` or the UI as needed.
8. Open a PR `ws-001/bootstrap-verification` only if you change anything.
   Otherwise close issue #1 with a comment summarizing the verification.
```

### Step-by-step
1. `gh repo clone Dynamo-Technologies/almighty && cd almighty`
2. Confirm scaffold present: `ls docs/ infra/ services/ web/ agents/ kernel/ czml/ .github/`.
3. Branch protection (org-owner only):
   ```bash
   gh api -X PUT repos/Dynamo-Technologies/almighty/branches/main/protection \
     -F required_status_checks.strict=true \
     -F required_status_checks.contexts='[]' \
     -F enforce_admins=false \
     -F required_pull_request_reviews.require_code_owner_reviews=true \
     -F required_pull_request_reviews.required_approving_review_count=1 \
     -F restrictions=
   ```
4. Project board status options: inspect with `gh project field-list 2 --owner Dynamo-Technologies --format json | jq '.fields[] | select(.name=="Status")'`. Add missing options via the GitHub UI (column rename is easiest in browser).
5. Close issue when verification done.

### Definition of done
- [ ] Repo exists with all three contributors having access.
- [ ] Initial directory scaffold committed.
- [ ] Project board live with all 32 WS-NNN issues.
- [ ] Status column shows Backlog → Ready → In Progress → Review → Done.

---

## WS-002 — Architecture diagram artifact

**Issue:** #2 · **Assignee:** @shanedynamo · **Blocked by:** #1 · **Parallel-safe with:** #3, #4

### Claude Code prompt

```
You are completing WS-002 (issue #2) in Dynamo-Technologies/almighty.

Commit the four-tier architecture diagram exported from the planning session
to docs/diagrams/architecture-v1.svg.

Steps:
1. Branch: ws-002/architecture-diagram
2. Place architecture-v1.svg at docs/diagrams/architecture-v1.svg. If you do
   not have the SVG yet, ask Shane for the planning-session export. Do not
   regenerate — use the locked artifact.
3. Verify the SVG includes:
   - All four tiers (Renderer, Orchestration, Agents, Kernel)
   - The cross-cutting concerns band
   - Two unclassified banners (top + bottom), light green (#C0DD97), dark
     font, ≤10px in the rendered diagram
4. Update docs/architecture.md (or create the stub if WS-003/WS-001 didn't
   land it) with `![Architecture v1](diagrams/architecture-v1.svg)` near the
   top.
5. Open a PR ws-002/architecture-diagram, request review from @alexcurnowdynamo
   and @devindynamo, link issue #2.
```

### Files
- `docs/diagrams/architecture-v1.svg` (new)
- `docs/architecture.md` (edit — add image reference)

### Definition of done
- [ ] Diagram in repo.
- [ ] Referenced from `docs/architecture.md`.
- [ ] Both unclassified banners present in SVG.

---

## WS-003 — Glossary and terminology lock

**Issue:** #3 · **Assignee:** @shanedynamo · **Blocked by:** #1 · **Parallel-safe with:** #2, #4

### Claude Code prompt

```
You are completing WS-003 (issue #3). Lock terminology for the entire project.

Create docs/glossary.md with these sections, fully populated. Every entry has
a one-line definition followed by 1–3 bullets of clarifying context. Where
the term has historically been confused (e.g., "Mzent" vs "MASINT"), call out
the corrected spelling and reject the wrong one explicitly.

Sections (in order):
1. Officer types — Sensor, Effector, Mover, Communicator, Commander.
2. Effect families — list all nine (EW cone, UAS corridor, radar fan,
   jamming circle, satellite swath, indirect fire arc, IR plume, MASINT cell,
   keyhole footprint).
3. Echelons — battalion, company, opfor mirror, white cell.
4. Tiers — Tier 1 Renderer, Tier 2 Orchestration, Tier 3 Agents, Tier 4 Kernel.
5. Override scopes — per-event, per-agent-per-turn, per-turn (with
   composability rule: per-event wins).
6. Cross-cutting concepts — capability profile, artifact, between-turn
   execution, unclassified banner, tenant isolation.

Branch ws-003/glossary, PR, link #3. After merge, every doc that references
these terms must point back to docs/glossary.md.
```

### Files
- `docs/glossary.md` (new)

### Definition of done
- [ ] Glossary committed.
- [ ] All five officer types, nine effect families, four echelons, four tiers, three override scopes defined.
- [ ] Subsequent issues reference `/docs/glossary.md`.

---

## WS-004 — Per-tenant AWS isolation IaC scaffold

**Issue:** #4 · **Assignee:** @alexcurnowdynamo · **Blocked by:** #1 · **Parallel-safe with:** #2, #3

### Claude Code prompt

```
You are completing WS-004 (issue #4). Author a Terraform module skeleton for
per-tenant AWS isolation. NO actual provisioning yet — module shape and
variable contracts only.

Path: infra/terraform/modules/tenant/

Module contract (per tenant):
- VPC subnet allocation (variable: parent_vpc_id, cidr_block)
- RDS Postgres instance (single instance, separate database — not schema)
- S3 bucket + KMS key (bucket name pattern: almighty-${tenant_id}-${env})
- ECS task family OR EKS namespace (gate behind a `runtime_mode` variable —
  decide one and document the other as TODO)
- IAM role per tenant with scoped-down policies

Files to author:
- main.tf — resource declarations (use `count = 0` or comment-only stubs so
  nothing applies; OR use `terraform validate`-only resources behind a
  `var.dry_run` flag — your choice, document it)
- variables.tf — all inputs with descriptions and types
- outputs.tf — vpc_subnet_id, rds_endpoint, s3_bucket_arn, kms_key_id,
  task_role_arn
- README.md — tenant lifecycle: provision → run → teardown. Include a worked
  example invocation.
- versions.tf — terraform >= 1.6, AWS provider ~> 5.0

Branch ws-004/tenant-iac-scaffold. Run `terraform fmt` and
`terraform validate` before pushing. PR, link #4.
```

### Files
- `infra/terraform/modules/tenant/{main,variables,outputs,versions}.tf`
- `infra/terraform/modules/tenant/README.md`

### Definition of done
- [ ] Module exists with input/output contracts documented.
- [ ] README explains tenant lifecycle (provision, run, teardown).
- [ ] `terraform validate` passes.

---

# Phase 1 — Schema, Kernel, Officer Interfaces

## WS-101 — Neutral entity/event schema

**Issue:** #5 · **Assignee:** @shanedynamo · **Blocked by:** #3 · **Parallel-safe with:** #6, #7

### Claude Code prompt

```
You are completing WS-101 (issue #5). Define the neutral entity/event schema
that DIS and HLA adapters both project from.

Deliverables:
1. docs/schema/entity-event.md — full schema spec.
   - Entity fields: entity_id (UUID), type taxonomy (enum + reference),
     position (lat/lon/alt + ECEF triple), kinematics (velocity vector,
     orientation quat), force affiliation (blue/red/white/neutral),
     capability_set_ref (FK to WS-106 capability profile id).
   - Event fields: event_id (UUID), tenant_id, scenario_id, turn (int),
     source_officer (officer type + entity_id), action_verb (enum from
     WS-105), payload (JSONB), causal_predecessors (array of event_id), ts.
   - Constraints: causal_predecessors must reference events in the same
     scenario_id. tenant_id + scenario_id form the namespace boundary.
   - Examples: 2 entity rows, 3 event rows.
2. kernel/schema/entities.sql — Postgres DDL for `entities` table with all
   columns, types, constraints, indexes (entity_id PK, tenant_id+scenario_id
   composite index).
3. kernel/schema/events.sql — DDL for `events` table, similar treatment.
4. kernel/schema/README.md — short note explaining that DDL stubs are not
   migrations yet (WS-301 owns migrations).

Branch ws-101/entity-event-schema, PR, link #5.
```

### Files
- `docs/schema/entity-event.md`
- `kernel/schema/entities.sql`, `kernel/schema/events.sql`, `kernel/schema/README.md`

### Definition of done
- [ ] Schema documented (field types, constraints, examples).
- [ ] DDL stubs committed.

---

## WS-102 — DIS PDU adapter contract

**Issue:** #6 · **Assignee:** @devindynamo · **Blocked by:** #5 · **Parallel-safe with:** #7

### Claude Code prompt

```
You are completing WS-102 (issue #6). Document the translation contract from
the WS-101 neutral schema to DIS PDU shapes. NO implementation — contract
and PDU family scope only.

Deliverable: docs/schema/dis-adapter.md

In-scope PDU families for v1 (justify each, exclude the rest):
- Entity State PDU
- Fire PDU
- Detonation PDU
- Signal PDU
- Transmitter PDU
- Receiver PDU

For each PDU family:
- Required fields and their source in the neutral schema.
- Field-level mappings table (Neutral field → PDU field → notes).
- Lossy mappings flagged explicitly (where DIS cannot represent something
  from the neutral schema, or vice versa).
- Open questions section for ambiguities (e.g., munition type taxonomy).

Cite the IEEE 1278.1 spec section numbers where helpful but do not paste
copyrighted text — link to public references only.

Branch ws-102/dis-adapter-contract, PR, link #6.
```

### Files
- `docs/schema/dis-adapter.md`

### Definition of done
- [ ] Adapter contract documented; no implementation.
- [ ] PDU family scope decided.

---

## WS-103 — HLA FOM adapter contract

**Issue:** #7 · **Assignee:** @devindynamo · **Blocked by:** #5 · **Parallel-safe with:** #6

### Claude Code prompt

```
You are completing WS-103 (issue #7). Document the translation contract from
the WS-101 neutral schema to HLA FOM shapes.

Deliverable: docs/schema/hla-adapter.md

Default to RPR-FOM v2.0 as the starting point. If you decide a custom FOM is
required, document the deviation and the v1 vs RPR-FOM delta.

For each RPR-FOM object/interaction class in scope:
- Class name (e.g., BaseEntity.PhysicalEntity.Platform.Aircraft).
- Mapping from neutral schema fields to FOM attributes.
- Subscribe/publish role from the perspective of the kernel (we are usually
  publisher for blue/red entities, subscriber for federate-supplied units).
- Lossy mappings flagged.

Same structure as WS-102. Branch ws-103/hla-adapter-contract, PR, link #7.
```

### Files
- `docs/schema/hla-adapter.md`

### Definition of done
- [ ] Adapter contract documented; no implementation.
- [ ] FOM choice (RPR-FOM v2.0 vs custom) decided.

---

## WS-104 — PyRapide DAG tenant/scenario namespacing

**Issue:** #8 · **Assignee:** @shanedynamo · **Blocked by:** #5 · **Parallel-safe with:** #9

### Claude Code prompt

```
You are completing WS-104 (issue #8). Extend the PyRapide DAG to namespace
events by (tenant_id, scenario_id). Confirm causal ordering is preserved
per scenario and that no cross-scenario event leakage is possible.

Steps:
1. Locate the upstream PyRapide DAG (Shane: confirm path/dependency before
   starting). Add as a submodule, pip dep, or vendored copy under kernel/.
2. Wrap or extend the DAG's commit/read APIs so every operation requires
   (tenant_id, scenario_id). Return a 1xx-level error / raise if missing.
3. Add an isolation invariant test: write events to scenario A, attempt to
   read them from scenario B in the same tenant — must return empty. Do the
   same across tenants.
4. Add a causal-ordering test: emit 5 events with explicit
   causal_predecessors, confirm topological iteration order matches the
   declared DAG.
5. Document in kernel/README.md: namespacing API, isolation guarantees,
   known limits (e.g., is rollback per-scenario? what about replay?).

Branch ws-104/dag-namespacing, PR, link #8.
```

### Files
- `kernel/` (PyRapide integration)
- `kernel/README.md`
- `kernel/tests/test_namespacing.py`

### Definition of done
- [ ] Namespacing implemented and unit-tested.
- [ ] Cross-scenario isolation verified.
- [ ] Cross-tenant isolation verified.

---

## WS-105 — Officer interface contracts (PyRapide vocabulary)

**Issue:** #9 · **Assignee:** @shanedynamo · **Blocked by:** #5 · **Parallel-safe with:** #8

### Claude Code prompt

```
You are completing WS-105 (issue #9). Define the five officer interfaces and
their 20 action verbs as a single canonical document.

Deliverable: docs/schema/officer-interfaces.md

For each verb, specify:
- Signature: parameter names, types, units (SI), required vs optional.
- Preconditions: what must be true before the verb can be issued (e.g.,
  Sensor.detect requires line-of-sight check; Effector.engage requires
  ammunition > 0 in capability profile).
- Emitted PyRapide event type: the event class/name in the DAG.
- Side effects: state mutations on the issuing entity, consumed resources.
- Failure modes: what causes rejection at the validator (capability gate),
  what causes rejection at runtime.

Structure the doc with one heading per officer type and a subheading per
verb. Include a summary table at the top.

Officer types and verbs:
- Sensor: detect, track, classify, lose_track
- Effector: engage, suppress, destroy, disable
- Mover: move_to, follow_route, halt, assume_posture
- Communicator: send, relay, jam, report
- Commander: issue_order, request_support, delegate, escalate

Cross-reference docs/glossary.md (WS-003) terminology. Branch
ws-105/officer-interfaces, PR, link #9.
```

### Files
- `docs/schema/officer-interfaces.md`

### Definition of done
- [ ] All 20 verbs documented with full signatures and event mappings.

---

## WS-106 — Capability profile schema

**Issue:** #10 · **Assignee:** @devindynamo · **Blocked by:** #9 · **Parallel-safe with:** #11

### Claude Code prompt

```
You are completing WS-106 (issue #10). Define the capability profile schema.

Deliverable: docs/schema/capability-profiles.md + a JSON Schema draft at
docs/schema/capability-profile.schema.json.

Schema structure:
- profile_id, version (immutable once scenario starts; see "Versioning"
  rule), display_name, force_affiliation
- officer_types_available: subset of {Sensor, Effector, Mover,
  Communicator, Commander}
- action_verbs_available: subset of the 20 verbs from WS-105
- effect_parameter_ranges: per-effect-family parameter bounds (min/max for
  ranges, kilowatt for EW, range_km for indirect fire, etc.) — this is what
  the validator (WS-202) enforces
- uncertainty: optional block, present only on red profiles. Encodes
  unknown-enemy uncertainty bands (e.g., effector range ±20%).
- entity_bindings: list of entity types or specific entity_ids that pull
  this profile.

Versioning rule: profile_id+version is immutable from scenario start
(turn 1) onward. Edits require a new profile_id (forking).

Provide two worked examples in the doc:
1. Notional US BCT (blue) — fully populated, no uncertainty.
2. Notional peer adversary (red) — uncertainty bands present on effector
   range, sensor range, jamming power.

Branch ws-106/capability-profile-schema, PR, link #10.
```

### Files
- `docs/schema/capability-profiles.md`
- `docs/schema/capability-profile.schema.json` (JSON Schema draft 2020-12)

### Definition of done
- [ ] Schema documented with two example profiles.

---

## WS-107 — Capability profile library — notional templates

**Issue:** #11 · **Assignee:** @shanedynamo · **Blocked by:** #10 · **Parallel-safe with:** #12

### Claude Code prompt

```
You are completing WS-107 (issue #11). Author four capability profile
templates as JSON files validated against the WS-106 schema.

Files (under kernel/capability-profiles/):
- us-bct.json
- peer.json
- near-peer.json
- hybrid-irregular.json

Each profile populates Sensor / Effector / Mover / Communicator / Commander
capabilities. Profiles include CZML param ranges per effect type they can
produce (this is what feeds WS-201 and WS-202).

Use unclassified, public, notional values. Do not reference any specific
real-world system by designation; use generic taxonomies ("medium-range
radar", "mid-tier indirect fire", "tactical jamming").

Validation:
- Run each profile through `ajv` (or python jsonschema) against the WS-106
  schema; commit only if all pass.
- Add a Makefile target or shell script `kernel/capability-profiles/validate.sh`
  that re-validates all four profiles.

Branch ws-107/capability-profile-library, PR, link #11.
```

### Files
- `kernel/capability-profiles/{us-bct,peer,near-peer,hybrid-irregular}.json`
- `kernel/capability-profiles/validate.sh`

### Definition of done
- [ ] Four profile JSON files validated against WS-106 schema.

---

## WS-108 — Effect artifact taxonomy

**Issue:** #12 · **Assignee:** @devindynamo · **Blocked by:** #9 · **Parallel-safe with:** #10, #11

### Claude Code prompt

```
You are completing WS-108 (issue #12). Define the artifact structure and
taxonomy.

Deliverable: docs/schema/artifacts.md

Artifact base fields:
- artifact_id (UUID)
- source_event_id (FK to WS-101 event)
- owning_entity (entity_id)
- capability_profile_ref (FK to WS-106)
- time_validity { start, end } — inclusive on start, exclusive on end
- czml_template_binding (template name from WS-201)
- adjudication_state — enum: { proposed, accepted, rejected, contested,
  resolved }

Map nine spatial effect families to artifact subtypes (each gets its own
subtype block in the doc with its specific parameter set):
1. EW cone
2. UAS corridor
3. Radar fan
4. Jamming circle
5. Satellite swath
6. Indirect fire arc
7. IR plume
8. MASINT cell
9. Keyhole footprint

Plus four non-spatial artifact types (no CZML binding):
- Order
- Report
- Comms traffic
- Intel assessment

For each subtype, list: required additional fields, expected adjudication
flow (auto-accept vs review vs always-contested), references back to
WS-105 verbs that emit it.

Branch ws-108/artifact-taxonomy, PR, link #12.
```

### Files
- `docs/schema/artifacts.md`

### Definition of done
- [ ] All nine spatial artifact types documented.
- [ ] Four non-spatial artifact types documented.

---

# Phase 2 — CZML Template Library

## WS-201 — CZML template library — base structures

**Issue:** #13 · **Assignee:** @alexcurnowdynamo · **Blocked by:** #12 · **Parallel-safe with:** #14

### Claude Code prompt

```
You are completing WS-201 (issue #13). Implement nine base CZML packet
templates.

Path: czml/templates/

Files (one per template):
- ew-cone.czml.json
- uas-corridor.czml.json
- radar-fan.czml.json
- jamming-circle.czml.json
- satellite-swath.czml.json
- indirect-fire-arc.czml.json
- ir-plume.czml.json
- masint-cell.czml.json
- keyhole-footprint.czml.json

Each template has three top-level blocks:
- base: the static CZML packet skeleton (id, name, availability, position
  defaults).
- params: parameter placeholders (use Mustache-style {{tokens}}) for
  position, time intervals, color, range, bearing — whatever the family
  requires.
- capability_constraints: parameter ranges per WS-106 (min/max, units). This
  is what WS-202 reads to validate.

Quality bars:
- Each file passes the Cesium CZML JSON schema (use `czml-validator` npm
  package or equivalent — link in README).
- Each template renders correctly in a smoke-test Resium scene. Provide a
  one-page test harness at czml/templates/_smoke-test.html that loads each
  template with sample params filled in.

Commit czml/templates/README.md describing the template format and adding
each file to a contents table.

Branch ws-201/czml-template-library, PR, link #13.
```

### Files
- `czml/templates/<nine .czml.json files>`
- `czml/templates/_smoke-test.html`
- `czml/templates/README.md`

### Definition of done
- [ ] All nine templates render in a smoke-test Resium scene.

---

## WS-202 — Capability-gated CZML validator

**Issue:** #14 · **Assignee:** @devindynamo · **Blocked by:** #13, #11 · **Parallel-safe with:** #15

### Claude Code prompt

```
You are completing WS-202 (issue #14). Build the capability-gated CZML
validator service.

Path: services/czml-validator/

Stack: Python 3.11+, FastAPI (or simple library + tiny HTTP wrapper —
your choice; document it).

API surface:
- validate(packet: dict, agent_id: str, capability_profile: dict) ->
  Result(accepted: bool, reasons: list[str])

Logic:
1. Look up the template referenced by `packet.template_id` in
   czml/templates/.
2. Pull capability_constraints for that template.
3. Cross-reference with the supplied capability profile's
   effect_parameter_ranges for the same effect family.
4. For each constrained parameter in the packet, confirm the value is in
   the intersection of (template range, profile range). Reject with the
   first violating reason.
5. Verify the agent (by agent_id) has the action_verb that emits this
   effect family (lookup in profile.action_verbs_available).

Tests (services/czml-validator/tests/):
- Unit tests for each of the four notional profiles from WS-107: feed in
  every effect family the profile should support and confirm acceptance;
  feed in one out-of-range value per family and confirm rejection with the
  right reason string.
- A pytest fixture loads the WS-107 profiles from disk so tests stay in sync.

Commit services/czml-validator/README.md with the API contract and how to
run tests (`pytest`).

Branch ws-202/czml-validator, PR, link #14. Notify @${ALEX} (renderer side)
that this contract is now stable.
```

### Files
- `services/czml-validator/{src,tests,README.md}`

### Definition of done
- [ ] Validator unit-tested against all four WS-107 profiles.

---

## WS-203 — Static CZML effect catalog (Nashville)

**Issue:** #15 · **Assignee:** @alexcurnowdynamo · **Blocked by:** #13 · **Parallel-safe with:** #16

### Claude Code prompt

```
You are completing WS-203 (issue #15). Hand-author one CZML packet per
effect template, geographically separated over Nashville. This file is a
visual regression test and template documentation.

Output: czml/demos/effect-catalog.czml

Layout: place the nine effects in a 3x3 grid roughly centered on Nashville,
with each effect ~3 km from the next so they don't overlap. Use notional but
realistic parameters (e.g., EW cone azimuth 045°, range 40 km; jamming
circle radius 8 km; satellite swath 200 km wide; indirect fire arc 25 km).

Time:
- Use availability for the full file: 2026-04-25T00:00:00Z to
  2026-04-25T01:00:00Z.
- Each effect activates at a slightly different time so they are
  individually inspectable when scrubbing the timeline.

The file must:
- Render in Resium without any kernel involvement (pure static CZML).
- Pass the Cesium CZML schema validator.
- Carry the unclassified banner in any renderer that loads it (banner is the
  renderer's responsibility — WS-501 — but mention this is required in
  comments inside the file or alongside it).

Branch ws-203/effect-catalog, PR, link #15.
```

### Files
- `czml/demos/effect-catalog.czml`

### Definition of done
- [ ] Effect catalog renders all nine effects visibly distinct over Nashville.

---

## WS-204 — Static CZML Nashville mini vignette

**Issue:** #16 · **Assignee:** @alexcurnowdynamo · **Blocked by:** #13 · **Parallel-safe with:** #15

### Claude Code prompt

```
You are completing WS-204 (issue #16). Author a ~10-minute scripted Cumberland
River crossing slice as a single CZML file.

Output: czml/demos/nashville-vignette.czml

Sequence (each effect activates at the listed offset; each lasts long enough
to overlap the next so the scene reads as continuous):
- T+00:00 — Red UAS corridor opens (UAS corridor effect, west-to-east over
  the river).
- T+01:00 — Red EW cone activates (azimuth 270°, on west bank).
- T+02:00 — Blue radar fan detects (east bank, sweeping west).
- T+03:00 — Blue indirect fire arc responds (impact point: river crossing).
- T+04:00 — MASINT cell registers signature (small footprint at impact).
- T+05:00 — Satellite swath passes overhead (broad, transient).
- T+06:00 — IR plume from impact (vertical, at impact point, decays over
  ~90 s).
- T+07:00 — Keyhole footprint refines (smaller polygon over impact).
- T+08:00 — Jamming circle covers crossing (red, ~5 km radius).

Total duration ~10 min from T+00:00 to T+10:00.

Anchor coordinates: Cumberland River north of downtown Nashville (~36.18°N,
86.78°W). Place each effect at a coordinate that is geographically
plausible for the scenario.

Branch ws-204/nashville-vignette, PR, link #16.
```

### Files
- `czml/demos/nashville-vignette.czml`

### Definition of done
- [ ] Vignette plays back coherently in Resium.
- [ ] All nine effect families exercised at least once.
- [ ] Banner present (in containing renderer).

---

# Phase 3 — Multi-Tenant Control Plane

## WS-301 — Tenant registry and RBAC service

**Issue:** #17 · **Assignee:** @alexcurnowdynamo · **Blocked by:** #4, #5 · **Parallel-safe with:** #18

### Claude Code prompt

```
You are completing WS-301 (issue #17). Build the tenant registry + RBAC REST
API.

Path: services/control-plane/

Stack: Node 20 + Fastify + TypeScript + pg (postgres). Justify any
substitutions in README.

Endpoints:
- POST   /tenants                — create tenant
- GET    /tenants                — list tenants the caller can see
- GET    /tenants/:id            — read
- PATCH  /tenants/:id            — update
- DELETE /tenants/:id            — soft-delete (set status=archived)
- POST   /tenants/:id/scenarios  — create scenario in tenant
- GET    /tenants/:id/scenarios  — list
- GET    /tenants/:id/scenarios/:sid — read
- PATCH  /tenants/:id/scenarios/:sid — update
- DELETE /tenants/:id/scenarios/:sid — soft-delete

Auth:
- JWT bearer with claims: tenant_id, cell_role (white | blue | red |
  observer).
- Cell-role enforcement:
  - white: full CRUD within own tenant.
  - blue/red: read scenarios; cannot modify other-cell state.
  - observer: read-only on scenarios; tenant list returns own tenant only.
- Cross-tenant access is impossible by construction — every query is
  parameterized on tenant_id pulled from the JWT, never from the URL.

DB:
- Apply WS-101 entity/event DDL plus a `tenants` table and a `scenarios`
  table. Migrations under services/control-plane/migrations/ using
  node-pg-migrate.

Tests:
- Integration test: spin up postgres, create two tenants, attempt
  cross-tenant reads — confirm denial.
- Cell-role matrix tested per endpoint.

Branch ws-301/control-plane-tenant-rbac, PR, link #17.
```

### Files
- `services/control-plane/{src,tests,migrations,README.md,package.json,tsconfig.json}`

### Definition of done
- [ ] API live in dev environment.
- [ ] Tenant isolation verified end-to-end.

---

## WS-302 — Turn controller (white cell only)

**Issue:** #18 · **Assignee:** @alexcurnowdynamo · **Blocked by:** #17, #8 · **Parallel-safe with:** #19

### Claude Code prompt

```
You are completing WS-302 (issue #18). Build the turn advancement endpoint,
white-cell-only.

Add to services/control-plane/ (same service as WS-301):

Endpoint: POST /tenants/:id/scenarios/:sid/turns/advance
- Auth: requires cell_role=white in JWT.
- Idempotency: if a turn advance is in progress, return 409.

Behavior on advance:
1. Lock current turn — set scenarios.turn_state = 'advancing', persist.
2. Trigger between-turn agent execution (WS-401). Until WS-401 ships, call
   a stub that just sleeps 100 ms and returns success — leave a clear
   `// TODO WS-401: replace stub with real call` comment.
3. Apply overrides (WS-303). Until WS-303 ships, no-op with a TODO.
4. Snapshot state — write a row to `turn_snapshots` table with
   (tenant_id, scenario_id, turn, snapshot_json, created_at). snapshot_json
   captures all entities + last N events for that turn.
5. Open next turn — increment scenarios.current_turn, set turn_state = 'open'.
6. Emit a turn_state event onto the WebSocket fan-out (WS-304). Until
   WS-304 ships, no-op with a TODO.

State snapshot persistence: keep all snapshots indefinitely in v1 (branching
and rollback are future work).

Tests:
- Stubbed end-to-end: advance from turn 1 to 2 to 3, confirm each snapshot
  exists and current_turn is correct.
- Auth test: blue/red/observer JWTs all return 403.

Branch ws-302/turn-controller, PR, link #18.
```

### Files
- `services/control-plane/src/turn-controller/`
- `services/control-plane/migrations/<next>_turn_snapshots.sql`

### Definition of done
- [ ] Full turn cycle executes end-to-end with stub agents.
- [ ] Snapshots verifiable in storage.

---

## WS-303 — Override gateway and policy plane

**Issue:** #19 · **Assignee:** @alexcurnowdynamo · **Blocked by:** #17 · **Parallel-safe with:** #18, #20

### Claude Code prompt

```
You are completing WS-303 (issue #19). Build the override policy object and
enforcement gateway.

Add to services/control-plane/ (same service):

Data model:
- table override_policies(id, tenant_id, scenario_id, scope, target_id,
  action, ttl_turns, rationale, created_by, created_at)
  - scope: 'per-event' | 'per-agent-per-turn' | 'per-turn'
  - target_id: event_id (per-event), agent_id+turn (per-agent-per-turn),
    turn (per-turn) — store as a polymorphic JSONB if cleaner
  - action: 'review' | 'auto-approve' | 'auto-block'
  - ttl_turns: integer; 0 means single-turn validity, >0 lasts that many

Endpoints:
- POST   /tenants/:id/scenarios/:sid/overrides         — author policy
- GET    /tenants/:id/scenarios/:sid/overrides         — list active
- DELETE /tenants/:id/scenarios/:sid/overrides/:oid    — revoke
- POST   /tenants/:id/scenarios/:sid/events/:eid/decision — manual decision

Gateway behavior:
- Intercept agent-emitted events BEFORE DAG commit (in-process or via a
  queue — document choice).
- For each event, look up applicable policies in this composability order:
  per-event > per-agent-per-turn > per-turn. First match wins. If no policy,
  default to 'review' (block until white cell ack).
- Action = auto-approve → commit to DAG.
- Action = auto-block → reject, record rejection event in DAG.
- Action = review → publish to override_pending WebSocket channel; block
  commit until manual decision endpoint hit.

Audit: every override decision (auto and manual) gets an `override_decision`
event written to the DAG so the AAR (WS-506) can render it.

Tests:
- Composability: three policies stacked; per-event wins.
- TTL: per-turn policy expires after N turns.
- Manual review: blocked until decision event posted.

Branch ws-303/override-gateway, PR, link #19.
```

### Files
- `services/control-plane/src/override-gateway/`
- `services/control-plane/migrations/<next>_override_policies.sql`

### Definition of done
- [ ] Three override scopes demonstrably enforced.
- [ ] Composability verified (per-event wins).

---

## WS-304 — WebSocket fan-out service

**Issue:** #20 · **Assignee:** @alexcurnowdynamo · **Blocked by:** #17 · **Parallel-safe with:** #18, #19

### Claude Code prompt

```
You are completing WS-304 (issue #20). Tenant-scoped WebSocket fan-out.

Path: services/websocket/

Stack: Node 20 + ws (or Fastify-websocket) + Redis pub/sub for fan-out
between instances. Justify substitutions.

Channels (per tenant):
- events           — DAG event broadcast (write-through from kernel).
- override_pending — pauses agent commits until white cell ack.
- turn_state      — turn lifecycle notifications.
- czml_packets    — live CZML stream to renderer.

Connection auth:
- Client sends JWT in Sec-WebSocket-Protocol header or as a query param
  (document the choice).
- Server validates, extracts tenant_id + cell_role, attaches to connection.
- Subscribe message: { channel: "events" }. Server enforces channel access
  per cell_role:
  - events: all roles in tenant.
  - override_pending: white only.
  - turn_state: all roles.
  - czml_packets: all roles.

Cross-talk prevention: every published message includes tenant_id; the
fan-out filter only delivers if connection.tenant_id === message.tenant_id.

Backpressure: drop-oldest if a connection's send queue exceeds 10 MB; log
the drop event.

Stress test:
- Spin up 4 simulated tenants, each with 8 connections, each sending 100
  msg/sec. Confirm:
  - Zero cross-tenant delivery.
  - p95 latency < 200 ms within tenant.
  - No leaks (process RSS stable over 5 min).

Branch ws-304/websocket-fanout, PR, link #20.
```

### Files
- `services/websocket/{src,tests,README.md,package.json}`

### Definition of done
- [ ] Channels broadcast within tenant only.
- [ ] Stress test: 4 concurrent tenants, no cross-talk.

---

# Phase 4 — Agents

## WS-401 — Between-turn agent execution harness

**Issue:** #21 · **Assignee:** @devindynamo · **Blocked by:** #8, #9, #18 · **Parallel-safe with:** #22

### Claude Code prompt

```
You are completing WS-401 (issue #21). Build the worker pool for between-turn
agent execution.

Path: agents/runtime/

Stack: Python 3.11+, CrewAI, Celery (or RQ — justify). Redis as broker.

Architecture:
- One worker process per tenant (no shared CrewAI process across tenants).
  Spawned on-demand when a tenant has a scenario in 'advancing' state.
- Workers pick up jobs from a tenant-scoped queue:
  almighty:tenant:{tenant_id}:turn-jobs
- Job payload: { tenant_id, scenario_id, turn, crew: 'blue'|'red'|'white' }.
- Sequential execution within a turn: blue → red → white adjudicator. The
  turn controller (WS-302) enqueues all three; the harness enforces order
  via Celery chains.
- On crew completion, harness POSTs back to control plane:
  /tenants/:id/scenarios/:sid/turns/:turn/crews/:crew/done

Isolation:
- Each worker reads only its tenant's queue; verify with namespace matchers.
- Worker has its own AWS role assumption (via WS-004 task_role_arn).

Empty crew test: harness can run a no-op crew end-to-end (start → finish
signal) in < 2 seconds.

Branch ws-401/agent-runtime-harness, PR, link #21.
```

### Files
- `agents/runtime/{src,tests,README.md,pyproject.toml}`

### Definition of done
- [ ] Harness runs an empty crew end-to-end and signals completion to turn controller.

---

## WS-402 — Officer interface tools (PyRapide event emitters)

**Issue:** #22 · **Assignee:** @devindynamo · **Blocked by:** #9, #14 · **Parallel-safe with:** #21

### Claude Code prompt

```
You are completing WS-402 (issue #22). Build CrewAI tool wrappers for each of
the 20 officer verbs.

Path: agents/tools/

Stack: Python 3.11+, CrewAI BaseTool subclasses.

Structure:
- tools/sensor/{detect,track,classify,lose_track}.py
- tools/effector/{engage,suppress,destroy,disable}.py
- tools/mover/{move_to,follow_route,halt,assume_posture}.py
- tools/communicator/{send,relay,jam,report}.py
- tools/commander/{issue_order,request_support,delegate,escalate}.py

Each tool class:
- Subclasses crewai.BaseTool.
- Pulls its signature from docs/schema/officer-interfaces.md (WS-105).
- On _run(): builds the corresponding CZML packet (if effect-emitting), calls
  services/czml-validator (WS-202) to gate it, and on accept emits a
  PyRapide event into the tenant+scenario namespace via the kernel's
  commit API (WS-104). On reject, raises ToolError(reason).
- NEVER mutates state directly — all state changes go through PyRapide
  events.

Capability gating: the tool checks the calling agent's
capability_profile.action_verbs_available BEFORE attempting validation. If
the verb is not allowed, raise immediately without calling the validator.

Tests (agents/tools/tests/):
- Each of the 20 tools callable from a mock CrewAI agent.
- Validator rejection paths exercised: feed an effector tool an
  out-of-range parameter, confirm the rejection bubbles up cleanly.

Branch ws-402/officer-tools, PR, link #22.
```

### Files
- `agents/tools/{tools/<five subdirs>,tests,README.md,pyproject.toml}`

### Definition of done
- [ ] All 20 tools callable from a CrewAI agent in test harness.
- [ ] Validator rejection paths exercised.

---

## WS-403 — Blue battalion crew stubs

**Issue:** #23 · **Assignee:** @devindynamo · **Blocked by:** #21, #22 · **Parallel-safe with:** #24, #25

### Claude Code prompt

```
You are completing WS-403 (issue #23). Author the blue battalion CrewAI crew
stubs.

Path: agents/blue/

Agents to define (one per file):
- s2.py — S2 Intelligence. Fuses sensor artifacts, maintains red COP,
  issues PIR-driven collection requests.
- s3.py — S3 Operations. Translates commander intent → orders, sequences
  effects, manages tempo.
- s6.py — S6 Signal. Manages comms posture, responds to EW/jamming,
  reroutes traffic.
- co_a.py, co_b.py, co_c.py — three company commanders executing S3 orders
  at the company level.

Each agent has:
- Tool access scoped to its officer types only:
  - S2: Sensor.* tools.
  - S3: Commander.* tools.
  - S6: Communicator.* tools.
  - Company commanders: Mover.* + Effector.* + Communicator.* tools.
- Goal and backstory doctrinally appropriate for a US BCT defending the
  Cumberland River. Public, unclassified doctrine references only.
- Bound to the us-bct.json capability profile (WS-107).

Crew composition: agents/blue/crew.py wires S2 → S3 → companies → S6 in a
between-turn sequential process. The crew runs once per turn when invoked
by the harness (WS-401).

Tests:
- crew runs one full between-turn cycle producing valid PyRapide events
  (no validator rejections in the happy path).

Branch ws-403/blue-crew, PR, link #23.
```

### Files
- `agents/blue/{s2,s3,s6,co_a,co_b,co_c,crew}.py`
- `agents/blue/tests/`

### Definition of done
- [ ] Crew runs one full between-turn cycle producing valid PyRapide events.

---

## WS-404 — Red OpFor crew stubs

**Issue:** #24 · **Assignee:** @devindynamo · **Blocked by:** #21, #22 · **Parallel-safe with:** #23, #25

### Claude Code prompt

```
You are completing WS-404 (issue #24). Mirror the blue echelon for OpFor.

Path: agents/red/

Same officer structure as WS-403: s2, s3, s6, three company commanders.

Differences from blue:
- Doctrinal flavor configurable per scenario via env or scenario config:
  RED_DOCTRINE = 'peer' | 'near-peer' | 'hybrid'. The flavor swaps the
  agents' backstories and goals, not their tool access.
- Bound to the matching capability profile (peer.json, near-peer.json, or
  hybrid-irregular.json from WS-107).
- Uncertainty bands from the red profile must be exercised: when the agent
  reasons about its own effector range, it should reflect the bounded
  uncertainty (e.g., "engage at 30-50 km" rather than a single value). The
  validator (WS-202) clamps to the upper bound.

Tests:
- Crew runs one full between-turn cycle for each of the three doctrines.
- Uncertainty path: red s3 issues an order that requires effector_range to
  resolve through the uncertainty band; confirm the resulting CZML packet's
  range parameter is within the validator-accepted clamp.

Branch ws-404/red-crew, PR, link #24.
```

### Files
- `agents/red/{s2,s3,s6,co_a,co_b,co_c,crew}.py`
- `agents/red/tests/`

### Definition of done
- [ ] Crew runs one full between-turn cycle producing valid PyRapide events.
- [ ] Uncertainty bands exercised.

---

## WS-405 — White cell adjudicator agent

**Issue:** #25 · **Assignee:** @devindynamo · **Blocked by:** #21, #22, #19 · **Parallel-safe with:** #23, #24

### Claude Code prompt

```
You are completing WS-405 (issue #25). Build the white cell adjudicator agent.

Path: agents/white-cell/

Single agent (adjudicator.py) plus a thin crew wrapper (crew.py) so it
plugs into the harness like blue/red.

Behavior:
- Runs after blue and red crews complete in a turn.
- Reads the turn's pending events from the override gateway's
  `review`-status queue.
- For each contested or ambiguous effect (e.g., "did the EW cone actually
  degrade comms?"), proposes a resolution by emitting a `proposed_resolution`
  event with rationale.
- High-stakes events (configurable predicate; default: any
  Effector.destroy or Effector.disable on a population center) NEVER
  auto-commit. The agent flags `human_required = true` on the proposed
  resolution and the override gateway holds the event until a white cell
  operator clicks through.

Stake classification:
- Implement stake_level(event) -> 'low' | 'medium' | 'high'. Document
  heuristic in agents/white-cell/README.md.
- The high-stakes path is the contract; medium and low can auto-commit
  proposed resolutions through the gateway with action='auto-approve'.

Tests:
- Contested-effect scenario fixture: feed a synthetic blue/red event pair
  where outcomes differ; adjudicator produces a single proposed_resolution.
- High-stakes path: synthetic destroy event → human_required=true,
  gateway state confirms held.

Branch ws-405/adjudicator-agent, PR, link #25.
```

### Files
- `agents/white-cell/{adjudicator,crew}.py`
- `agents/white-cell/{tests,README.md}`

### Definition of done
- [ ] Adjudicator handles a contested-effect test scenario.
- [ ] High-stakes path requires human ack.

---

# Phase 5 — Renderer

## WS-501 — Resium scaffold

**Issue:** #26 · **Assignee:** @alexcurnowdynamo · **Blocked by:** #1 · **Parallel-safe with:** #2, #3, #4

### Claude Code prompt

```
You are completing WS-501 (issue #26). Build the Resium app shell.

Path: web/renderer/

Stack: Vite + React 18 + TypeScript + Resium + Cesium. PNPM as package
manager.

Tasks:
1. Scaffold a Vite app under web/renderer/.
2. Cesium ion token wiring:
   - Read CESIUM_ION_TOKEN from import.meta.env.
   - Provide a self-hosted-assets fallback path. Document the choice in
     web/renderer/README.md (default: ion).
3. Load Nashville terrain and imagery. Camera initial position centered
   on (36.18°N, 86.78°W), altitude 8 km, looking down.
4. Banner component (web/renderer/src/components/Banner.tsx):
   - Top + bottom strip, full width.
   - Background #C0DD97, dark text (#111), font-size 10px.
   - Text: "UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY".
   - Always rendered on every route — put it in App.tsx around <Outlet/>.
5. Tenant-aware routing shell:
   - Routes: /:tenantId/scenarios/:scenarioId. NO logic yet — just the
     shape. Render placeholder components.
6. EXCON layout primitives (web/renderer/src/layouts/Excon.tsx):
   - Sidebar (left), map canvas (center), action panel (right).
   - CSS Grid, no logic yet.

Smoke test: `pnpm dev` boots, navigate to /demo/scenarios/demo, confirm
Nashville terrain visible and both banners present.

Branch ws-501/resium-scaffold, PR, link #26.
```

### Files
- `web/renderer/{src,public,index.html,vite.config.ts,tsconfig.json,package.json}`

### Definition of done
- [ ] App boots, shows Nashville.
- [ ] Banners present top and bottom.

---

## WS-502 — Static CZML loader

**Issue:** #27 · **Assignee:** @alexcurnowdynamo · **Blocked by:** #26, #15, #16 · **Parallel-safe with:** #28

### Claude Code prompt

```
You are completing WS-502 (issue #27). Make the renderer load and play
either of the static CZML files.

Add to web/renderer/:

Components:
- src/components/CzmlSelector.tsx — toggle between catalog and vignette.
- src/components/CzmlLoader.tsx — accepts a URL, fetches CZML, mounts as a
  Resium <CzmlDataSource>.

Data sources:
- czml/demos/effect-catalog.czml (WS-203)
- czml/demos/nashville-vignette.czml (WS-204)

Wire-up:
1. Copy or symlink the two CZML files into web/renderer/public/czml/ at
   build time (Vite plugin or a simple npm script).
2. Add a dev-only toggle (top-right corner, behind a `?dev=1` query param)
   that switches between the two.
3. On switch, unmount the previous data source cleanly.

No live data yet — this is the static path only.

Branch ws-502/static-czml-loader, PR, link #27.
```

### Files
- `web/renderer/src/components/{CzmlSelector,CzmlLoader}.tsx`
- `web/renderer/public/czml/` (copied at build)

### Definition of done
- [ ] Both static CZML files render correctly in the live app.

---

## WS-503 — Live PyRapide CZML adapter

**Issue:** #28 · **Assignee:** @devindynamo · **Blocked by:** #27, #14, #20 · **Parallel-safe with:** #29

### Claude Code prompt

```
You are completing WS-503 (issue #28). Build the live adapter that translates
PyRapide DAG events into CZML packets.

Path: services/czml-adapter/

Stack: Python 3.11+ (joint owners @devindynamo + @alexcurnowdynamo).

Logic:
1. Subscribe to the tenant's `events` channel on the WebSocket fan-out
   service (WS-304).
2. For each event with a CZML-bound artifact (per WS-108 taxonomy):
   a. Look up the template in czml/templates/ (WS-201).
   b. Substitute params from the event payload + capability profile.
   c. Send the proposed packet to services/czml-validator/ (WS-202).
   d. On accept, publish the CZML packet to the tenant's `czml_packets`
      channel.
   e. On reject, log + emit a `czml_rejected` event into the DAG so AAR
      can show the rejection.
3. Handle deletion events (effect ended) by publishing CZML packets with
   `delete: true`.

Renderer-side update (web/renderer/):
- Replace WS-502's static-only loader with a live/static toggle. In live
  mode, subscribe to czml_packets WebSocket and apply each packet via the
  Resium <CzmlDataSource>'s incremental load API.

Tests:
- End-to-end happy path: publish a synthetic event → validator accepts →
  packet appears on czml_packets → renderer shows the effect.
- Capability gating: publish an event with out-of-range params → validator
  rejects → no packet on the channel → effect does not render.

Joint PR ws-503/live-czml-adapter (kernel side: services/czml-adapter; web
side: web/renderer/src/components/LiveCzmlSubscriber.tsx). Link #28.
```

### Files
- `services/czml-adapter/{src,tests,README.md,pyproject.toml}`
- `web/renderer/src/components/LiveCzmlSubscriber.tsx`

### Definition of done
- [ ] Live adapter renders effects from a running scenario.
- [ ] Capability gating verified (rejected packets do not render).

---

## WS-504 — EXCON consoles (blue, red)

**Issue:** #29 · **Assignee:** @alexcurnowdynamo · **Blocked by:** #26, #17 · **Parallel-safe with:** #28, #30

### Claude Code prompt

```
You are completing WS-504 (issue #29). Build order entry UI for blue and red
operators.

Add to web/renderer/:

Routes:
- /:tenantId/scenarios/:scenarioId/excon/blue
- /:tenantId/scenarios/:scenarioId/excon/red

Both routes render the EXCON layout (WS-501) with:
- Sidebar: list of friendly entities under the operator's command.
- Map canvas: live CZML (WS-503) plus a click-to-target overlay.
- Action panel: order entry form bound to the 20 officer interface verbs
  (WS-105). Form is dynamic — picks fields from the verb's signature.

Effect preview:
- When the operator drafts an order that emits a CZML-bound effect, render
  a ghost preview on the map (50% opacity) using the same template that
  WS-503 will eventually publish.

Turn state:
- Display current turn number, "open" vs "advancing" indicator.
- Lock-out the order entry form when state is 'advancing'.

Auth:
- Pull tenant_id + cell_role from the JWT.
- Refuse to render the blue route if cell_role !== 'blue' (ditto red).
  Show "ACCESS DENIED — wrong cell role" message.

Banner present (inherited from WS-501).

Branch ws-504/excon-consoles, PR, link #29.
```

### Files
- `web/renderer/src/routes/excon/{blue,red}/`
- `web/renderer/src/components/{OrderForm,EffectPreview,TurnState}.tsx`

### Definition of done
- [ ] Operators can issue orders that produce valid PyRapide events via the agent runtime.

---

## WS-505 — White cell console

**Issue:** #30 · **Assignee:** @alexcurnowdynamo · **Blocked by:** #26, #18, #19, #11 · **Parallel-safe with:** #29

### Claude Code prompt

```
You are completing WS-505 (issue #30). Build the white cell control surface.

Add to web/renderer/:

Route: /:tenantId/scenarios/:scenarioId/white-cell

Surface (vertical sections, scroll if needed):
1. Turn advancement: button "Advance Turn" — POSTs to WS-302's endpoint;
   disabled while turn_state === 'advancing'. Shows latest snapshot timestamp.
2. Override policy authoring (WS-303):
   - Form: scope (per-event | per-agent-per-turn | per-turn), target_id,
     action (review | auto-approve | auto-block), ttl_turns, rationale.
   - Active policies table with revoke action.
3. Capability profile authoring (WS-107 schema):
   - JSON editor (Monaco or react-jsonschema-form). Load existing profile,
     edit, save. Pre-scenario only — locked at turn 1.
4. Override review queue: incoming events on `override_pending` WebSocket
   channel. For each, surface the proposed effect, agent identity, capability
   profile, validator result. Buttons: Approve, Block, Edit-and-approve,
   Inject-manual.
5. Adjudication surface: events flagged human_required=true by WS-405.
   Same approve/block flow as review queue but visually distinct.

Auth: cell_role must be 'white'. Otherwise render "ACCESS DENIED".

Banner present (inherited from WS-501).

Branch ws-505/white-cell-console, PR, link #30.
```

### Files
- `web/renderer/src/routes/white-cell/`
- `web/renderer/src/components/{TurnControls,OverridePolicyForm,ProfileEditor,ReviewQueue,AdjudicationSurface}.tsx`

### Definition of done
- [ ] White cell can author profiles, set policies, advance turns, intercept overrides end-to-end.

---

## WS-506 — AAR replay

**Issue:** #31 · **Assignee:** @alexcurnowdynamo · **Blocked by:** #28, #18

### Claude Code prompt

```
You are completing WS-506 (issue #31). Build the AAR (after-action review)
replay surface.

Add to web/renderer/:

Route: /:tenantId/scenarios/:scenarioId/aar

Capabilities:
1. Timeline scrubber spanning the full scenario duration. Tick marks per
   turn. Drag to seek.
2. Playback at variable speed: 0.5x, 1x, 2x, 4x, 8x, 16x. Pause/play.
3. Replay over committed DAG events:
   - Pull events from a new endpoint /tenants/:id/scenarios/:sid/events
     (add to control-plane if missing).
   - Re-issue them through the live CZML adapter (WS-503) running in
     replay mode (no kernel mutations, just translation).
4. Override decisions visible inline:
   - Markers on the timeline at every override_decision event.
   - Click a marker to see the full record (scope, action, rationale,
     decided_by).
5. Export to per-tenant S3:
   - "Export AAR" button uploads a packaged bundle (events JSON + CZML
     stream + override log + a generated PDF summary) to the tenant's S3
     bucket from WS-004.
   - Bucket path: s3://almighty-${tenant_id}-${env}/aar/${scenario_id}/.
6. Banner must remain visible throughout playback AND in the exported PDF.

Branch ws-506/aar-replay, PR, link #31.
```

### Files
- `web/renderer/src/routes/aar/`
- `web/renderer/src/components/{TimelineScrubber,PlaybackControls,OverrideMarkers,AarExport}.tsx`

### Definition of done
- [ ] Completed Nashville vignette scenario can be replayed end-to-end.
- [ ] Override audit visible.

---

# Phase 6 — Demo Vignette Integration

## WS-601 — Nashville Cumberland River crossing scenario

**Issue:** #32 · **Assignee:** @shanedynamo · **Blocked by:** #23, #24, #25, #28, #29, #30

### Claude Code prompt

```
You are completing WS-601 (issue #32) — the integration capstone.

This is a scripted demo scenario that exercises the full platform:
- Blue defends the west bank of the Cumberland River.
- Red attempts a forced crossing with combined arms + EW + UAS.

Path: agents/scenarios/nashville-cumberland-crossing/

Files:
1. scenario.yaml — declarative scenario config:
   - tenant_id (use a fixed demo tenant)
   - scenario_id
   - blue_capability_profile: us-bct.json (WS-107)
   - red_capability_profile: peer.json (WS-107)
   - terrain anchor: 36.18°N, 86.78°W
   - duration_turns: 6
   - red doctrine: peer
2. pre-scenario.md — operator runbook for the white cell:
   - profiles to author (already in WS-107, just confirm)
   - override policies pre-set: per-event review for all
     Effector.destroy/disable events; per-turn auto-approve for everything
     else for turns 1-3; manual review for turns 4-6.
3. assertions.md — observability checklist for the demo run:
   - All nine effect families exercised at least once across the scenario.
   - At least one human override decision recorded.
   - Adjudicator (WS-405) flagged at least one high-stakes event.
   - Final AAR (WS-506) exports to S3 successfully.

Execution steps for the demo:
1. White cell operator opens https://app.almighty.demo/demo/scenarios/nashville/white-cell.
2. Authors capability profiles (or confirms pre-loaded).
3. Sets override policies per pre-scenario.md.
4. Starts scenario by enqueuing turn 1.
5. Blue and red operators sit in the EXCON consoles (WS-504) issuing orders.
6. Adjudicator runs each turn end (WS-405); white cell reviews flagged events.
7. After turn 6, white cell opens AAR (WS-506) and exports.

Recording: a stakeholder-facing recording is the final demo deliverable.
Place under demos/recordings/ on per-tenant S3 (out of repo).

Branch ws-601/nashville-vignette-integration, PR, link #32.
```

### Files
- `agents/scenarios/nashville-cumberland-crossing/{scenario.yaml,pre-scenario.md,assertions.md}`

### Definition of done
- [ ] Scenario runs to completion across multiple turns.
- [ ] All nine effect families exercised.
- [ ] AAR exportable.
- [ ] Demo recordable for stakeholders.

---

## Closing notes

- Every issue's body in the GitHub repo already contains the canonical
  scope, deps, and DoD. This document is a *companion* — when the issue
  body and this file disagree, the issue body wins.
- When a Claude Code session starts a WS-NNN, paste the prompt block from
  this file as the very first message. Then add as a follow-up: "open issue
  #N in browser, read deps, branch off main, proceed."
- Update this file when an issue's scope materially changes during
  execution (rare). Otherwise treat as build-time-only reference.
