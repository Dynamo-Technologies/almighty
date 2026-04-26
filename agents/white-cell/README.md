# `almighty-white-cell` — WS-405

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

The white-cell adjudicator agent. Runs after blue (WS-403) and red
(WS-404) crews complete in a between-turn cycle, classifies each
pending event by stake, and proposes a resolution that the WS-303
override gateway either commits (low / medium) or holds for human ack
(high).

## What it is

A single agent — not a six-role staff like blue/red. The adjudicator
sits outside the blue/red structure, doesn't issue officer verbs (its
tool-set is empty), and reads events emitted by the other crews. Its
output is one :class:`Decision` per input event, mapping onto the
WS-303 ``override_decisions`` audit table:

| Decision field | Meaning |
|---|---|
| `event_id` | UUID of the source event being adjudicated. |
| `action_verb`, `source_officer_type` | Echoed from the source for AAR readability. |
| `stake` | `low` / `medium` / `high`. See [§ Stake heuristic](#stake-heuristic). |
| `outcome` | `auto-approve` (low/medium) or `review-pending` (high). |
| `human_required` | `True` for `review-pending`. |
| `contested` | `True` when the event conflicts with another event in the same turn. |
| `rationale` | Human-readable explanation, written to the audit row. |
| `conflicts_with` | Event IDs this decision is contested against. |

## Stake heuristic

v1 default (override via the `stake_predicate` argument):

| Stake | Trigger |
|---|---|
| **high** | `action_verb == 'destroy'` (always). OR `payload.stake == 'high'` (stamped by the WS-402 `DestroyTool` and any future high-stakes emitter). OR adjudication-flagged verb (`engage`, `disable`, `jam`) when target/area is sensitive: `target_force_affiliation == 'NEUTRAL'`, `target_is_civilian == True`, `population_center == True`, or `civilian_band_overlap == True`. |
| **medium** | Effector + EW area effects without sensitive-target signals (`engage`, `suppress`, `jam`, `disable`). |
| **low** | Sensor reads, Mover position changes, Communicator messages (non-EW), Commander orders / requests / delegations / escalations. |

> **Why not "destroy on a population center"?** The runbook hints that as the high-stakes default, but WS-101's entity schema does not yet carry a `population_center` flag (an open question I flagged in the WS-108 review). v1 surfaces the runbook's intent through caller-annotated payload fields (`target_is_civilian`, `target_force_affiliation`, `population_center`) instead. The Nashville WS-601 scenario will likely supply a custom `StakePredicate` that consults a named-area-of-interest map.

The high-stakes path is the **contract** — a custom predicate may broaden it but should never downgrade an obviously-high event without scenario-specific reason. Tests confirm a `destroy` event that's also `contested` still routes to `review-pending` (high stake wins).

## Contested-effect detection

The default `contested_predicate` flags an event as contested when:

1. `payload.contested == True` (caller-set marker), OR
2. `payload.adjudication_state == 'contested'` (per WS-108 § 2 enum), OR
3. Another event in the same batch targets the same `target_entity_id` from the same turn.

(3) catches the canonical "did the EW cone actually degrade comms?" case the runbook calls out — overlapping claims on the same target entity. The adjudicator emits **one Decision per event** (not one merged); each contested event names its conflicts via `conflicts_with`.

## API contract

```python
from almighty_kernel.dag import KernelEvent
from almighty_white_cell import adjudicate_events, Decision

events: list[KernelEvent] = ...  # union of blue + red commits this turn
decisions: list[Decision] = adjudicate_events(events)

# Or with a custom heuristic:
def my_stake(e):
    if "OBJ-CIVILIAN" in e.payload.get("target_label", ""):
        return "high"
    return "medium" if e.action_verb in ("engage", "suppress") else "low"

decisions = adjudicate_events(events, stake_predicate=my_stake)
```

For harness integration, the convenience runner matches Shane's `CrewRunner` signature:

```python
from almighty_agent_runtime.crews import CrewContext
from almighty_white_cell import run_white_crew

result = run_white_crew(CrewContext(tenant_id="...", scenario_id="...", turn=1))
# CrewResult(crew='white', metadata={'events_in': 6, 'decisions': [...], ...})
```

The v1 runner manufactures a synthetic 6-event batch (3 routine + 2 contested-pair + 1 high-stakes destroy) so the harness can exercise both DoD scenarios end-to-end without depending on a queue surface that WS-401 doesn't expose yet. v2 will pull pending events from the harness queue.

## Integration with WS-303 override gateway

In v1 the adjudicator does **not** POST decisions to the control-plane HTTP service — it returns Decisions and lets the caller wire them. When the integration ticket lands (after all three crews are merged), the caller will:

1. For each Decision with `outcome == 'auto-approve'`: the gateway's `evaluateEvent` already returns `auto-approve`, no extra POST needed.
2. For each Decision with `outcome == 'review-pending'`: POST to `POST /tenants/:id/scenarios/:sid/events/:eid/decision` per WS-303, but using `outcome = 'review-pending'` to signal human review needed (the adjudicator is the producer; the white cell operator via WS-505 is the eventual decider).

Until that integration, the v1 runner's metadata.decisions list is the contract surface — anyone consuming it gets the same shape the gateway will eventually persist.

## Run

```bash
# From this directory (agents/white-cell/):
python3.13 -m venv .venv
source .venv/bin/activate

# Install editable deps in topological order:
pip install -e ../../kernel
pip install -e ../runtime
pip install -e ".[dev]"

# Run the test suite:
pytest -v
```

## Tests — 25 passing

- **`test_stakes.py`** (12 tests): stake_level for every verb and sensitive-target signal — destroy always high, payload markers, neutral / civilian / civilian-band overlap, medium/low defaults.
- **`test_adjudicator.py`** (7 tests): per-decision flow — auto-approve for low; review-pending + human_required for high; contested-pair yields two Decisions with mutual conflicts_with; high-stakes-AND-contested still holds for human ack; custom stake predicate honored; decision order matches event order.
- **`test_crew.py`** (6 tests): end-to-end via `run_white_crew(ctx)` against the synthetic 6-event batch — confirms both DoD scenarios (contested-pair + high-stakes destroy holds for human ack), routine events auto-approve, runner export is callable.

Real `KernelEvent` instances throughout — no mocks of upstream contracts.

## Layout

```
agents/white-cell/
├── pyproject.toml
├── README.md                                     ← this file
├── src/almighty_white_cell/
│   ├── __init__.py                               ← exports adjudicate_events, Decision, stake_level, WHITE_RUNNER
│   ├── stakes.py                                 ← stake_level(event), StakePredicate type
│   ├── adjudicator.py                            ← Decision, adjudicate_events(events, *, stake_predicate, contested_predicate)
│   └── crew.py                                   ← run_white_crew(ctx), WHITE_RUNNER, synthetic event batch
└── tests/
    ├── conftest.py                               ← crew_ctx fixture, make_event helper
    ├── test_stakes.py
    ├── test_adjudicator.py
    └── test_crew.py
```

## Notes / open questions

- **No HTTP integration with the override gateway in this PR.** The adjudicator returns Decisions; wiring them to the WS-303 service is a follow-up (matches the same scope-discipline I've used for blue / red crew → WS-401 harness).
- **No `population_center` lookup.** WS-101 entity schema lacks the field; v1 reads caller-annotated payload signals. The scenario-specific predicate is the right escape hatch until an entity-side flag lands.
- **Adjudicator is single-agent, not a Crew.** The `_build_adjudicator_agent` constructor returns one `crewai.Agent` for parity with blue / red. There's no `crewai.Crew` constructed in v1 because the adjudicator doesn't run a multi-agent process.
- **v1 doesn't read events from the harness queue.** It manufactures a synthetic batch in `_synthetic_events`. v2 will replace this with a pull from the WS-401 harness's commit queue once that queue surface exists.
- **Empty tool-set is intentional.** The adjudicator does not issue officer verbs. Its output is the Decision list, written to `override_decisions` by the gateway.

## See also

- [`docs/schema/officer-interfaces.md`](../../docs/schema/officer-interfaces.md) — verb signatures (WS-105).
- [`docs/schema/artifacts.md`](../../docs/schema/artifacts.md) — adjudication state machine + flow categories (WS-108 § 2-3).
- [`services/control-plane/`](../../services/control-plane/) — override gateway (WS-303).
- [`services/control-plane/migrations/1763676000003_override-policies.sql`](../../services/control-plane/migrations/1763676000003_override-policies.sql) — the `override_decisions` table this agent's Decisions map onto.
- [`agents/blue/`](../blue/) — WS-403 blue crew.
- [`agents/red/`](../red/) — WS-404 red crew.
- WS-505 (#30) — white-cell console where human operators act on `review-pending` decisions.
- WS-601 (#32) — Nashville scenario; will supply a scenario-specific `stake_predicate`.
