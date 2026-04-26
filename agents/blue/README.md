# `almighty-blue-crew` — WS-403

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

CrewAI agents for the blue battalion in the Nashville Cumberland River
crossing scenario. Six roles, all bound to the
[`us-bct.json`](../../kernel/capability-profiles/us-bct.json) capability
profile (WS-107):

| Role | Officer types | Verbs in scope |
|---|---|---|
| **S2 Intelligence** | SENSOR | `detect`, `track`, `classify`, `lose_track` |
| **S3 Operations** | COMMANDER | `issue_order`, `request_support`, `delegate`, `escalate` |
| **S6 Signal** | COMMUNICATOR | `send`, `relay`, `report` (no `jam` — us-bct doesn't authorize it) |
| **Co A** | MOVER + EFFECTOR + COMMUNICATOR | left flank — `move_to`, `engage`, `send`, … |
| **Co B** | MOVER + EFFECTOR + COMMUNICATOR | center / main effort over the crossing |
| **Co C** | MOVER + EFFECTOR + COMMUNICATOR | right flank, frequent reposition |

Each agent's goal and backstory key off public unclassified doctrine
(FM 3-21.20, ATP 3-90.5, ATP 2-01.3) and the Cumberland River
geography. No specific real-world weapon system is named.

## What the v1 crew is — and what it isn't

The v1 crew is **deterministic**. Each role is a real `crewai.Agent`
with the proper `role` / `goal` / `backstory` / `tools` so the agent
SHAPE matches what an LLM-driven loop will need later. But the
between-turn execution is a scripted Python sequence that calls each
tool's `_run()` directly in the WS-105 order.

This satisfies the DoD ("crew runs one full between-turn cycle
producing valid PyRapide events") without burning API keys or
introducing nondeterminism into the test suite. v2 swaps in
`Crew.kickoff()` once LLM access and cost / latency budgets are sorted;
the spec files (`s2.py`, `s3.py`, etc.) are already shaped for it.

## Between-turn sequence

```
S2.detect          (RADAR contact on red UAS-equivalent)
    ↓
S2.classify        (refine into a typed classification)
    ↓
S3.issue_order     (MOVE order to Co A)
    ↓
S3.request_support (ISR request to higher echelon)
    ↓
Co A.assume_posture(DUG_IN)
    ↓
Co A.send          (SITREP to S3 over VHF)
    ↓
Co B.halt          (commit to defensive line)
    ↓
Co B.suppress      (indirect-fire suppression on east-bank NAI)
    ↓
Co C.move_to       (slight reposition north)
    ↓
S6.send            (HF comms-status to BRIGADE_S6)
    ↓
S6.report          (SITREP to BRIGADE)
```

11 tool calls per cycle → 11 KernelEvents committed through
`NamespacedDag.commit()`. Officer-type distribution: 2 SENSOR, 2
COMMANDER, 3 MOVER, 1 EFFECTOR, 3 COMMUNICATOR.

## API contract

```python
from almighty_agent_runtime.crews import CrewContext
from almighty_blue_crew import run_blue_crew

ctx = CrewContext(
    tenant_id="11111111-1111-4111-8111-111111111111",
    scenario_id="22222222-2222-4222-8222-222222222222",
    turn=1,
)
result = run_blue_crew(ctx)
# CrewResult(crew='blue', duration_ms=…, notes='v1 deterministic blue crew — 11 events committed', metadata={...})
```

`metadata.steps` is a list of `{step, event_id, verb, officer_type,
validator}` rows in execution order. `metadata.validator_rejections` is
guaranteed `0` for the happy path; any reject would have raised
`ToolError` and aborted the cycle.

## Integration with WS-401 harness

The v1 crew matches Shane's `CrewRunner = Callable[[CrewContext],
CrewResult]` signature and exports `BLUE_RUNNER`. The WS-401 harness's
`BLUE_CREWS["default"]` is currently the no-op stub; a follow-up ticket
will swap it for `BLUE_RUNNER`:

```python
# In agents/runtime/src/almighty_agent_runtime/crews.py:
from almighty_blue_crew import BLUE_RUNNER
BLUE_CREWS["default"] = BLUE_RUNNER
```

That swap is intentionally NOT in this PR — it should land when WS-403
/ WS-404 / WS-405 all exist so the harness has all three crews live
together.

## Why the crew is self-contained (instantiates its own DAG + Validator)

Shane's `CrewContext` carries only `(tenant_id, scenario_id, turn)`.
The crew needs more (capability profile, kernel DAG, validator) and
those pieces are not yet plumbed through the harness. Rather than
extend Shane's contract from this PR, the v1 crew **instantiates a
fresh `NamespacedDag` and `Validator` per call** and attributes events
to synthetic per-role `agent_entity_id`s.

This means events committed in a run are LOST when the function
returns. That's acceptable for the v1 stub DoD ("produces valid
PyRapide events" — production, not persistence is the bar). v2 wires
the harness-supplied DAG handle through a richer context; entity
bindings will land alongside.

## Run

```bash
# From this directory (agents/blue/):
python3.13 -m venv .venv
source .venv/bin/activate

# Install editable deps in topological order:
pip install -e ../../kernel
pip install -e ../../services/czml-validator
pip install -e ../runtime
pip install -e ../tools
pip install -e ".[dev]"

# Run the test suite:
pytest -v
```

## Tests — 5 passing

- **`test_crew_runs_one_full_cycle`** — the DoD test. One call →
  11 events committed, zero validator rejections.
- **`test_every_step_has_an_event_id`** — every step result carries a
  unique `event_id`.
- **`test_officer_type_distribution`** — the 11 events split across
  officer types as the script predicts (2 SENSOR / 2 COMMANDER / 3
  MOVER / 1 EFFECTOR / 3 COMMUNICATOR).
- **`test_every_step_validator_field_set`** — every step declares
  `accepted` (CZML-emitting) or `skipped` (non-spatial); at least one
  `accepted` so the validator path was exercised end-to-end.
- **`test_runner_export_is_callable`** — `BLUE_RUNNER` matches Shane's
  `CrewRunner` signature for the eventual WS-401 swap.

## Layout

```
agents/blue/
├── pyproject.toml
├── README.md                                       ← this file
├── src/almighty_blue_crew/
│   ├── __init__.py                                 ← exports run_blue_crew, BLUE_RUNNER
│   ├── doctrine.py                                 ← Cumberland River anchors, doctrine refs
│   ├── profile.py                                  ← us-bct.json loader (cached)
│   ├── s2.py, s3.py, s6.py                         ← role spec modules (ROLE/GOAL/BACKSTORY/ALLOWED_VERBS)
│   ├── co_a.py, co_b.py, co_c.py                   ← company commander spec modules
│   └── crew.py                                     ← orchestration + deterministic script
└── tests/
    ├── conftest.py
    └── test_crew.py
```

## Notes / open questions

- **No `disable` verb in us-bct.** us-bct.json does not include `disable`
  in `action_verbs_available`, so the company commanders' `ALLOWED_VERBS`
  declare `engage`/`suppress`/`destroy` only. If a future profile
  variant adds `disable`, update the company spec files.
- **No `jam` verb in us-bct.** S6's `ALLOWED_VERBS` omits `jam` for the
  same reason. The role's backstory explains the defensive posture;
  the `Communicator.bands` block on us-bct still declares max-power
  ranges per band, but the verb gate prevents emission.
- **`destroy` is high-stakes.** Companies have `destroy` in their
  allowed set, but the v1 script does NOT call `destroy` — that path
  is reserved for the WS-405 adjudicator's
  `human_required = true` flow once the white cell is live.
- **Doctrinal sources.** Backstories cite FM 3-21.20, ATP 3-90.5, ATP
  2-01.3 explicitly. If WS-403 grows specific tool callouts (e.g.,
  named weapon families), keep them generic per the
  better-late-than-never doc's project-conventions rules.

## See also

- [`docs/schema/officer-interfaces.md`](../../docs/schema/officer-interfaces.md) — verb signatures (WS-105).
- [`docs/schema/capability-profiles.md`](../../docs/schema/capability-profiles.md) — profile schema (WS-106).
- [`kernel/capability-profiles/us-bct.json`](../../kernel/capability-profiles/us-bct.json) — the bound profile (WS-107).
- [`agents/tools/`](../tools/) — the 20 officer tool wrappers (WS-402).
- [`agents/runtime/`](../runtime/) — the harness this crew plugs into (WS-401).
- WS-404 (#24) — red OpFor crew, sibling.
- WS-405 (#25) — white cell adjudicator, sibling.
