# `almighty-officer-tools` — WS-402

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

CrewAI tool wrappers for each of the 20 officer interface verbs locked
in [`docs/schema/officer-interfaces.md`](../../docs/schema/officer-interfaces.md)
(WS-105). Sits between agents (WS-403 / WS-404 / WS-405) and the kernel:

```
agent → OfficerTool._run(...) → capability gate → validator → kernel.commit()
```

Tools never mutate state directly. Every state change goes through
`almighty_kernel.NamespacedDag.commit()` per the
[better-late-than-never](../../docs/better-late-than-never.md) doc.

## What each tool does

For every call, in order:

1. **Capability-verb gate.** If the bound profile's
   `action_verbs_available` does not contain this tool's `VERB`, raise
   `ToolError` immediately — the validator is **never** consulted.
   Per WS-105 / runbook §1093.
2. **Args validation.** Pydantic schema (`args_schema`) parses the
   keyword args. Extra checks (e.g., `delegate.delegated_verbs ⊆
   own action_verbs_available`, `escalate.to_echelon` strictly higher,
   `send` requires recipient_entity_id XOR recipient_role) raise
   `ToolError` or `ValidationError` synchronously.
3. **Validator gate (CZML-emitting verbs only).** Build a params dict
   keyed on the template's `capability_constraints`, call the WS-202
   validator in-process. On `accepted=False`, raise
   `ToolError(reason)`.
4. **Kernel commit.** Build a `KernelEvent`, hand it to
   `NamespacedDag.commit()`. Returns `event_id`, the verb, the officer
   type, and the validator outcome (`accepted` / `skipped`).

Mover verbs (`move_to`, `follow_route`, `halt`, `assume_posture`),
Communicator non-spatial verbs (`send`, `report`, and `relay` when not
airborne or `advertise_corridor=false`), and all four Commander verbs
**skip** the validator step. Their effect family is `None`.

## API contract

```python
from uuid import UUID

from almighty_czml_validator import Validator
from almighty_kernel.dag import NamespacedDag

from almighty_officer_tools import OfficerToolContext, build_all_tools

ctx = OfficerToolContext(
    tenant_id=UUID("..."),
    scenario_id=UUID("..."),
    turn=0,
    agent_entity_id=UUID("..."),
    capability_profile=us_bct_profile_dict,    # WS-106 / WS-107 shape
    kernel_dag=NamespacedDag(),
    validator=Validator(),                      # in-process
)

tools = build_all_tools(ctx)                   # name-keyed dict, 20 entries

result = tools["engage"]._run(
    target_entity_id=UUID("..."),
    weapon_system="notional.indirect.medium",
    volume_count=4,
    range_m=10_000.0,
    time_of_flight_s=25.0,
)
# {'event_id': '...', 'verb': 'engage', 'officer_type': 'EFFECTOR', 'validator': 'accepted'}
```

`build_all_tools` is the convenience entry. WS-403 / WS-404 / WS-405
will typically construct the **subset** of tools each crew agent needs
(Sensor-only S2 agent gets the four Sensor tools; company commanders
get Mover + Effector + Communicator).

### Verb-by-verb tool inventory

| Officer | Verb | EFFECT_FAMILY | Notes |
|---|---|---|---|
| Sensor | `detect` | per-modality | `EO_IR` → none; `RF` → `ew_cone`; `RADAR` → `radar_fan`; ACOUSTIC/SEISMIC/MASINT_MULTI → `masint_cell`. |
| Sensor | `track` | none | Continuation; no spatial artifact. |
| Sensor | `classify` | `keyhole_footprint` | Tighter footprint scales with dwell. |
| Sensor | `lose_track` | none | |
| Effector | `engage` | `indirect_fire_arc` | Args mutually-exclusive: target entity XOR coord. |
| Effector | `suppress` | `indirect_fire_arc` | `mode='suppression'` on the event payload. |
| Effector | `destroy` | `indirect_fire_arc` | Adds `stake='high'` to payload for WS-405 adjudicator. |
| Effector | `disable` | per-method | `KINETIC` → `indirect_fire_arc`; `EW` → `jamming_circle`; `CYBER` → none. |
| Mover | `move_to` | none | |
| Mover | `follow_route` | none | |
| Mover | `halt` | none | No args. |
| Mover | `assume_posture` | none | Posture-transition validity is a downstream profile check. |
| Communicator | `send` | none | recipient_entity_id XOR recipient_role. |
| Communicator | `relay` | conditional | Emits `uas_corridor` only when `is_airborne=True` AND `profile.communicator.advertise_corridor=True`. |
| Communicator | `jam` | `jamming_circle` | Polygon ≥ 3 vertices; v1 always omni-circle (directional `ew_cone` is a v2 dispatch). |
| Communicator | `report` | none | |
| Commander | `issue_order` | none | to_entity_id XOR to_echelon. |
| Commander | `request_support` | none | FIRES / MEDEVAC require target coord. |
| Commander | `delegate` | none | `delegated_verbs ⊆ own action_verbs_available` (rejects with `ToolError`). |
| Commander | `escalate` | none | `to_echelon` strictly higher than profile.commander.echelon (rejects sideways/downward). |

## What downstream crews must respect

These are the constraints lifted out of WS-105, the glossary, and
[better-late-than-never](../../docs/better-late-than-never.md). They are
not enforced by the harness — they're agent-author responsibilities:

- **The 20-verb vocabulary is locked.** If a crew needs a 21st verb,
  open an issue against WS-105 first. Don't add an ad-hoc tool.
- **`destroy` is its own verb, not an `engage` flag.** The override
  gateway (WS-303) and adjudicator (WS-405) key off the verb name. Use
  `destroy` when you mean it.
- **Mover verbs emit no spatial artifacts.** Don't author a "movement"
  artifact family. Position updates flow through the live adapter
  (WS-503) which reads entity-state changes directly.
- **`escalate` is strictly upward.** Sideways escalation is rejected as
  a control-flow trick.
- **`force_affiliation = RED` is a precondition for `uncertainty`.**
  Knowledge of an opponent's bands belongs to the opposing side's
  profile.

## Run

```bash
# From this directory (agents/tools/):
python3.13 -m venv .venv
source .venv/bin/activate

# Install editable deps in topological order (kernel and validator first):
pip install -e ../../kernel
pip install -e ../../services/czml-validator
pip install -e ".[dev]"

# Run the test suite:
pytest -v
```

## Tests — 35 passing

- **One happy-path per verb** for the 20 verbs (some have multiple,
  e.g., `detect` exercises `RADAR` happy + `EO_IR` no-validator;
  `disable` exercises KINETIC + CYBER; `relay` exercises both
  airborne+corridor and non-airborne paths).
- **Reject paths** for: validator out-of-range (`detect` RADAR, `engage`
  range, `jam` power), capability gate (us-bct lacks `jam` and
  `disable`), `delegate` not-in-authority, `escalate`
  not-strictly-higher (sideways AND downward).
- **Sanity tests** for: 20 verbs registered with unique names, all
  classes subclass `crewai.tools.BaseTool`.

Profiles loaded fresh from `kernel/capability-profiles/` at session
start; each test uses a real in-memory `NamespacedDag` and the real
WS-202 `Validator`. No mocks of either: when a tool fires, it actually
commits to the DAG and actually consults the validator. Drift in either
upstream surfaces immediately on `pytest`.

## Layout

```
agents/tools/
├── pyproject.toml
├── README.md                                        ← this file
├── src/almighty_officer_tools/
│   ├── __init__.py                                  ← public exports
│   ├── context.py                                   ← OfficerToolContext, ToolError
│   ├── base.py                                      ← OfficerToolBase
│   ├── registry.py                                  ← build_all_tools, ALL_TOOL_CLASSES
│   ├── sensor/{detect,track,classify,lose_track}.py
│   ├── effector/{engage,suppress,destroy,disable}.py
│   ├── mover/{move_to,follow_route,halt,assume_posture}.py
│   ├── communicator/{send,relay,jam,report}.py
│   └── commander/{issue_order,request_support,delegate,escalate}.py
└── tests/
    ├── conftest.py                                  ← profile + DAG + validator fixtures
    ├── test_base.py                                 ← gate + structural sanity
    └── test_{sensor,effector,mover,communicator,commander}.py
```

## Notes / open questions

- **Posture transition matrix** (Mover.assume_posture): the validator
  doesn't yet enforce `posture_transitions` from the profile. v1 commits
  the event; the adjudicator (WS-405) is responsible for catching
  invalid transitions. If profile-side enforcement is needed sooner,
  add a check in `AssumePostureTool._build_event_payload`.
- **`disable.method=EW` validator path**: routes to `jamming_circle`,
  which means the *Effector* tool's commit goes through a
  *Communicator*-shaped template. v1 accepts that overlap; if WS-405
  needs to discriminate "EW disable" from "actual jam", it can use the
  source event's `action_verb` and `payload.method`.
- **Directional vs omni jammers**: the runbook hints that single-
  aperture directional platforms should emit `ew_cone` for `jam`. v1
  always uses `jamming_circle`; the dispatch is a follow-up when
  WS-201 templates pick up an `ew-cone` jamming variant.
- **CrewAI agent integration**: tests call `_run(**kwargs)` directly,
  bypassing the LLM-tool-call loop. That's the typical pattern for
  CrewAI tool unit tests. Real agent invocation happens in WS-403 /
  WS-404 / WS-405 when the crews are stood up.

## See also

- [`docs/schema/officer-interfaces.md`](../../docs/schema/officer-interfaces.md) — verb signatures (WS-105).
- [`docs/schema/capability-profiles.md`](../../docs/schema/capability-profiles.md) — profile schema (WS-106).
- [`docs/schema/artifacts.md`](../../docs/schema/artifacts.md) — verb→artifact mapping (WS-108).
- [`services/czml-validator/`](../../services/czml-validator/) — in-process validator (WS-202).
- [`kernel/almighty_kernel/dag.py`](../../kernel/almighty_kernel/dag.py) — `NamespacedDag.commit()` (WS-104).
- WS-403 (#23) / WS-404 (#24) / WS-405 (#25) — crews that consume these tools.
