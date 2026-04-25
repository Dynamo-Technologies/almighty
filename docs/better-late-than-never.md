# Better Late Than Never — implementation-time context

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

A running log of choices that mattered while WS-NNN issues were being
implemented but aren't necessarily obvious from reading the code or
issue bodies. Read this before opening a Claude Code session in this
repo — these are the gotchas that would otherwise eat a chunk of your
turn.

Entries are grouped by domain (toolchain, schemas, GitHub plumbing, etc.)
rather than by issue, because someone debugging Terraform doesn't care
which WS-NNN first hit the snag. Each entry tags the source WS for
deeper context.

---

## Toolchain

### macOS bash is 3.2; the runbook scripts need 4+

`/Users/<you>/Dev/assault-dash/planning/0[1-5]-*.sh` use `declare -A`
(associative arrays). System bash 3.2 fails with `unbound variable`
under `set -u`.

**Fix.** Install bash 5 from Homebrew and invoke explicitly:

```bash
brew install bash
/opt/homebrew/bin/bash ./01-setup-labels.sh
```

The shebang `#!/usr/bin/env bash` resolves to `/bin/bash` 3.2 on macOS.
Don't fight that — just call the new binary directly. Source: WS-001
runbook execution.

---

### Terraform 1.6+ requires the HashiCorp tap on macOS

The `homebrew/core` formula for `terraform` is **deprecated and frozen
at 1.5.7** because of the BUSL license switch. Our `versions.tf` requires
`>= 1.6`.

**Fix.** Swap binaries:

```bash
brew uninstall terraform
brew install hashicorp/tap/terraform
terraform version   # should report 1.14+ now
```

Or use OpenTofu (`brew install opentofu`, CLI is `tofu`) — same
configuration files, different binary name. We default to `terraform`
in `validate.sh` and CI scripts. Source: WS-004.

---

### Python 3.11+ for kernel work; macOS system python3 is 3.9

PyRapide requires Python ≥ 3.11. macOS' `/usr/bin/python3` is 3.9.
Homebrew typically has `/opt/homebrew/bin/python3.11`,
`python3.13`, `python3.14` already installed.

**Setup pattern used in the repo:**

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e kernel/
pytest kernel/tests/
```

Or just point a one-shot venv at `/tmp` if you don't want it in the
repo: `python3.13 -m venv /tmp/almighty-kernel-venv`. Source: WS-104.

---

### Validate scripts auto-provision `.venv`

`kernel/capability-profiles/validate.sh` checks if `python3` can `import
jsonschema`; if not, it creates a local `.venv/` and installs there. The
directory is gitignored.

This means **the first run is slow** (pip install) but subsequent runs
are fast. Don't be surprised by a one-time delay. Source: WS-107.

---

## GitHub plumbing

### `gh project field-edit` does not exist

The `gh` CLI has `field-create`, `field-delete`, `field-list` — but **no
`field-edit`**. To change the options on a single-select field (e.g.,
the project board's Status column), use the GraphQL API directly:

```bash
gh api graphql -f query='
mutation {
  updateProjectV2Field(input: {
    fieldId: "<PVTSSF_xxx>"
    singleSelectOptions: [
      { name: "Backlog",     color: GRAY,   description: "..." },
      { name: "Ready",       color: GREEN,  description: "..." },
      { name: "In Progress", color: YELLOW, description: "..." },
      { name: "Review",      color: BLUE,   description: "..." },
      { name: "Done",        color: PURPLE, description: "..." }
    ]
  }) { projectV2Field { ... on ProjectV2SingleSelectField { id name } } }
}'
```

Get the `fieldId` from `gh project field-list <N> --owner <org> --format
json`. Existing items keep their assignment if their option name still
exists in the new list. Source: WS-001.

---

### The default Project v2 Status options are NOT optional to replace

A fresh `gh project create` yields **Todo / In Progress / Done** as Status
options every time. The dummy-instructions WS-001 prompt says "configure
... if not already present" — read that as **always replace**, never as
"check first then maybe leave it." Source: WS-001 verification.

---

### `gh auth refresh` only takes effect if the browser flow completes

Running `gh auth refresh -h github.com -s admin:org,project,repo` and
seeing the existing scopes in `gh auth status` afterwards means the
browser flow was abandoned. The fix is a full re-login that reuses the
existing scopes plus the new ones:

```bash
gh auth login --hostname github.com --scopes "admin:org,project,repo,workflow,gist"
```

Verify with:

```bash
gh api -i user 2>&1 | grep -i x-oauth-scopes
```

Source: WS-001 setup.

---

### Branch protection is ON; every PR needs a non-self reviewer

`main` is protected: PR required, CODEOWNERS approval required (1
approving review), no force-push, no deletion. Two consequences worth
internalizing:

1. **You cannot merge directly to `main`.** A pre-existing `git push
   origin main` will be denied. Always branch and PR.
2. **You cannot approve your own PR.** GitHub blocks self-approval on
   any PR you opened, even if you are listed as a CODEOWNER for the
   touched paths. Most paths under `/docs/` and `/kernel/schema/` are
   owned by `@shanedynamo` per `.github/CODEOWNERS` — when Shane opens
   a PR there, the only paths to merge are: another codeowner approves,
   or admin override. The simplest in-flight pattern is to add both
   `@alexcurnowdynamo` and `@devindynamo` as reviewers on every PR
   regardless of who opened it.

Source: WS-001.

---

### Use `Closes #N` in the PR body

GitHub auto-closes issues when a PR with `Closes #N` (or `Fixes #N`,
`Resolves #N`) merges to the default branch. Saves a manual close step
and keeps the issue thread cleanly bound to the PR.

Pattern in the repo:

```markdown
## Summary
- ...

Closes #N.

## DoD
- [x] ...
```

Source: convention adopted from PR #34 onwards.

---

## Schema and data model

### Position is stored twice (geodetic + ECEF) and the kernel does NOT recompute

`entities` rows carry both WGS-84 lat/lon/alt AND ECEF x/y/z. Producers
keep them in sync to within 1 m. The kernel never recomputes one from
the other on the read path because every adapter projection (DIS,
HLA, CZML) wants one or the other ready-shaped, and re-projecting on
every read was a real perf risk.

If you're emitting events into the kernel, **fill both** at write time
or write a helper that does. Don't fill one and leave the other zeroed.
Source: WS-101.

---

### Composite FK `(tenant_id, scenario_id, source_entity_id)` is the strongest namespace barrier

Postgres can't FK across an array column (`causal_predecessors`) but it
*can* enforce that an event's `source_entity_id` exists in an entity row
in the **same** `(tenant_id, scenario_id)`. The DDL in `kernel/schema/
events.sql` does that with a composite FK pointing at a UNIQUE constraint
on `entities (tenant_id, scenario_id, entity_id)`.

Net effect: a malicious or buggy commit attempting to insert an event
referencing an entity in another tenant fails at the database level.
This is intentional and load-bearing — don't drop it.

Verification commands are in `kernel/schema/README.md`. Source: WS-101.

---

### Predecessor-cross-scenario trigger is declared but unattached

`kernel/schema/events.sql` defines `events_validate_predecessors()` but
the `CREATE TRIGGER` line is **commented out**. Application-side
enforcement (in `almighty_kernel.NamespacedDag.commit`) is the gate
today. WS-104 owns the decision to turn the trigger on after benchmarking
the per-event cost.

If you're wiring a new ingest path, **call the kernel commit method**.
Don't `INSERT INTO events` directly — you'll bypass the predecessor
check. Source: WS-101 + WS-104.

---

### `r` is not hex — beware mnemonic UUIDs

JSON Schema's `format: uuid` with `FormatChecker` runs Python's
`uuid.UUID()` parser, which requires `[0-9a-f]` only. The doc examples
in `docs/schema/capability-profiles.md` use `00000000-rrrr-…`. **Those
fail strict format-check.**

Workaround used in `kernel/capability-profiles/`:

| Profile | profile_id mnemonic |
|---|---|
| `us-bct.json` | `00000000-bbbb-0001-0000-000000000001` (BLUE → bbbb) |
| `peer.json` | `00000000-aaaa-0001-0000-000000000001` |
| `near-peer.json` | `00000000-cccc-0001-0000-000000000001` |
| `hybrid-irregular.json` | `00000000-dddd-0001-0000-000000000001` |

`a/b/c/d/e/f` are valid hex; `r/g/h/x` are not. If you author a new
profile, pick from the safe set. Source: WS-107.

---

### `entity_bindings.specific_ids` and `entity_bindings.type_subtype_refs` are an OR

The schema requires at least one of the two arrays to be present. If
both are present, both are honored: a specific entity_id wins over
type-pattern matching. Document this when adding profiles that need
specific-id pinning (e.g., the Cumberland River bridge defenders in the
WS-601 scenario will likely use `specific_ids` for known entity IDs).
Source: WS-106 / WS-107.

---

## PyRapide

### Installed as a pip dep, not vendored

PyRapide is published on PyPI as `pyrapide` (currently 0.3.0), authored
by Shane (`shane@beautifulmajesticdolphin.com`), repo at
`github.com/ShaneDolphin/pyrapide`. We consume it via
`kernel/pyproject.toml`'s `dependencies = ["pyrapide>=0.3.0", ...]`.

Don't vendor it. Don't add it as a git submodule. Just `pip install -e
kernel/` and the dep resolves cleanly. Source: WS-104.

---

### `caused_by` lives on the Poset, not on the Event

The PyRapide `Event` model has these fields: `id`, `name`, `payload`,
`source`, `timestamp`, `metadata`. **There is no `caused_by` attribute
on the Event itself.** Causal links are stored on the `Poset` as edges,
added via `Poset.add(event, caused_by=[predecessors])`.

This trips you up if you try `event.caused_by` and get an `AttributeError`.
The fix is to query the Poset:

```python
poset.causes(event)        # frozenset of immediate causes
poset.ancestors(event)     # transitive
poset.topological_order()  # full causal-ordered list
```

Source: WS-104.

---

### Namespace isolation is by separate Posets, not filtering

The Almighty wrapper holds `dict[(tenant_id, scenario_id) → Poset]`. A
read for namespace A literally cannot reach namespace B's Poset because
they're in different dict slots. There is **no shared event store** that
gets filtered after the fact.

This matters for any future feature that wants "cross-namespace queries"
— it's structurally impossible without explicit cross-Poset traversal,
and that's by design. Don't add a global event index. Source: WS-104.

---

## Terraform module

### Output `description` strings cannot interpolate variables

Terraform rejects `description = "Bucket name pattern: almighty-${var.tenant_id}-${var.env}."`
in an `output` block with `Variables not allowed`. Use placeholder text:

```hcl
description = "Bucket name pattern: almighty-<tenant_id>-<env>."
```

The variable values still flow through `value`, just not into
`description`. Source: WS-004.

---

### `dry_run` over hard-coded `count = 0`

Every resource in `infra/terraform/modules/tenant/main.tf` is gated by:

```hcl
locals {
  enabled = var.dry_run ? 0 : 1
}

resource "aws_subnet" "tenant_a" {
  count = local.enabled
  ...
}
```

Default is `dry_run = true`, so `terraform plan` produces an empty plan
and `apply` is a no-op until the calling root module passes
`dry_run = false`. This is preferable to `count = 0` directly because it
lets CI exercise variable validation without flipping a workspace into a
partial-apply state. Don't change the default. Source: WS-004.

---

### Single CIDR splits internally for two AZs

Module input is a single `cidr_block` per the WS-004 prompt. RDS
DB subnet groups require subnets in **two** AZs. The module uses
`cidrsubnet(var.cidr_block, 1, 0)` and `(…, 1, 1)` to split the input
into two `/28` halves.

Caller passes `/27` minimum. If you pass `/28` you'll get an error from
`cidrsubnet`. The README documents this. Source: WS-004.

---

## Project conventions

### MASINT, never "Mzent"

Measurement and Signature Intelligence. The `Mzent` form is a
transcription error from the planning session and is explicitly rejected
in `docs/glossary.md` § 2. Don't use it in code, comments, doc PRs, or
commit messages. Source: WS-003.

---

### The 20 verb vocabulary is locked

`docs/schema/officer-interfaces.md` is the single source of truth. The
matching CHECK constraint is staged as a TODO in `kernel/schema/events.sql`
ready to drop in once the doc is approved (WS-105 PR is open at the time
of writing).

If you need a 21st verb, **open an issue against WS-105 first**. Don't
add it ad-hoc to a tool wrapper or a profile. Source: WS-105.

---

### `destroy` is its own verb, not an `engage` flag

The model intentionally separates irreversibility. `destroy` always
carries `human_required = true` per WS-405; the override gateway and
white cell adjudicator key off the verb name. If you find yourself
wanting to "do an engage that also destroys," reach for `destroy`
instead and let the adjudicator gate it. Source: WS-105.

---

### Mover verbs emit no spatial artifacts

`move_to`, `follow_route`, `halt`, `assume_posture` produce no CZML
packets. Entity position updates flow through the live adapter (WS-503)
which reads entity-state changes directly. Don't add a "movement"
artifact family — it doesn't exist by design (it would flood the
artifact stream and the renderer already has a cheaper path). Source:
WS-105.

---

### `escalate` is strictly upward

`Commander.escalate.to_echelon` must be **strictly higher** than the
issuing entity's echelon. Sideways escalation is rejected at the
validator. This prevents `escalate` from being used as a generic
control-flow trick (e.g., "escalate to peer to bypass override
gateway"). Source: WS-105.

---

### `bands` and `channels` are independent in the communicator block

A profile can list a band in `communicator.bands` (and therefore `jam`
on it) without listing the matching channel in `communicator.channels`
(and therefore not be able to `send` on it). This asymmetry is
deliberate and exercised in `kernel/capability-profiles/hybrid-irregular.json`
(UHF in bands, not in channels).

If you reduce a profile's communicator capabilities, prune **both**
arrays — don't assume one implies the other. Source: WS-107.

---

### `force_affiliation = RED` is a precondition for `uncertainty`

The schema's `uncertainty` block is structurally allowed on any profile,
but the WS-202 validator rejects it on non-RED profiles at registration
time. If you're authoring a BLUE/WHITE/NEUTRAL profile and reach for
uncertainty bands, **stop**: that knowledge belongs to the *opposing*
side's profile, not yours. Source: WS-106 / WS-107.

---

## Verification habits worth keeping

### Verify SQL DDL against a scratch Postgres before committing

`kernel/schema/README.md` documents the docker recipe. The WS-101
verification turned up four constraint violations that the DDL caught
correctly (bad enum, non-unit quaternion, out-of-range latitude,
cross-namespace FK). Run the same recipe whenever you change DDL
shapes — Postgres' real validator is much sharper than reading the
SQL.

```bash
docker run --rm -d --name almighty-pg-scratch \
  -e POSTGRES_PASSWORD=scratch -p 5433:5432 postgres:16
docker exec -i almighty-pg-scratch psql -U postgres -d postgres < kernel/schema/entities.sql
docker exec -i almighty-pg-scratch psql -U postgres -d postgres < kernel/schema/events.sql
docker rm -f almighty-pg-scratch
```

Source: WS-101.

---

### Verify SVG banner artifacts before merging

Diagram PRs should grep the SVG for the banner color and count the
`UNCLASSIFIED` strings. The diagram has TWO banners (top + bottom):

```bash
SVG=docs/diagrams/architecture-v1.svg
grep -c '#C0DD97' "$SVG"
grep -oE 'UNCLASSIFIED' "$SVG" | wc -l   # must be 2
grep -oE 'font-size="[0-9]+"' "$SVG"     # must be ≤ 10
```

Catches a regenerated SVG that lost the banners or got the color wrong.
Source: WS-002.

---

## When in doubt

- **Issue body wins on disputes.** This file, `docs/architecture.md`,
  and even `docs/dummy-instructions.md` are companion references — when
  any of them disagrees with the upstream WS-NNN issue, the issue body
  is canonical.
- **Don't widen scope without an issue.** If implementing WS-X surfaces
  a needed change in WS-Y, open a follow-up issue. Don't bundle it.
  Reviewers can't track scope creep otherwise.
- **Add a section here when you find another gotcha.** This file is
  exactly the place. PRs that touch it don't need to be tied to a
  specific WS-NNN.
