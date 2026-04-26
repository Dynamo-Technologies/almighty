# `almighty-red-crew` — WS-404

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

CrewAI agents for the red opposing-force battalion attempting a forced
crossing of the Cumberland River. Mirrors the blue crew (WS-403) shape
but configurable across three doctrine flavors and bound to red
capability profiles whose uncertainty bands are actively exercised.

## Doctrine flavors

| Doctrine | Profile | Posture |
|---|---|---|
| `peer` (default) | [`peer.json`](../../kernel/capability-profiles/peer.json) | conventional combined-arms, sophisticated EW, balanced bands |
| `near-peer` | [`near-peer.json`](../../kernel/capability-profiles/near-peer.json) | constrained ammo / high-end systems, broader bands, more improvisation |
| `hybrid` | [`hybrid-irregular.json`](../../kernel/capability-profiles/hybrid-irregular.json) | irregular force, no formal staff, very wide bands on improvised systems |

Selection priority at run time:
1. Explicit `doctrine=` kwarg to `run_red_crew(...)`
2. `ALMIGHTY_RED_DOCTRINE` environment variable
3. Default `"peer"`

The flavor swaps each role's goal / backstory text and selects the
bound profile. Tool access (the per-role `ALLOWED_VERBS` set) does
**not** change with doctrine; the capability gate in WS-402 enforces
what the profile actually permits at run time.

## Roles

Same six as blue (WS-403): S2, S3, S6, Co A/B/C. Identical role-to-
officer-type mapping. Per-role bases (`BASE_GOAL`, `BASE_BACKSTORY`,
`ALLOWED_VERBS`) live in the role spec modules; per-doctrine flavor
text comes from `doctrine.py` via `assemble_goal` / `assemble_backstory`.

## What the v1 crew is — and isn't

Identical posture to WS-403: real `crewai.Agent` instances with full
shape, but the between-turn execution is a deterministic Python script
that calls each tool's `_run()` directly. v2 swaps in `Crew.kickoff()`
when LLM access is sorted.

## Between-turn sequence

Per-doctrine step counts:

| Doctrine | Steps |
|---|---|
| `peer` | 10 |
| `near-peer` | 10 |
| `hybrid` | 9 |

```
S2.detect (EO_IR — no spatial artifact, valid for all profiles)
  ↓
[peer / near-peer]                        [hybrid]
S3.issue_order (ATTACK to Co B)           S3.send_shadow (informal radio order)
S3.request_support (ISR)                  ─
  ↓                                         ↓
Co A.assume_posture(DISMOUNTED)
  ↓
Co A.send (SITREP to RED_BN_S3)
  ↓
Co B.halt
  ↓
Co B.engage (indirect fire on west-bank objective; UNCERTAINTY-REASONED)
  ↓
Co C.move_to (slight reposition northwest)
  ↓
S6.send (HF/VHF to RED_BRIGADE_S6)
  ↓
S6.report (SITREP to BRIGADE)
```

### Why the script differs from blue

| Difference | Why |
|---|---|
| `S2.detect` uses **EO_IR**, not RADAR | Hybrid lacks `radar_fan` in `effect_parameter_ranges`; EO_IR has no spatial artifact so it skips the validator path entirely. |
| `S2.classify` is **omitted entirely** | No red profile authorizes `keyhole_footprint` (the artifact `classify` always emits). v2 may add it once a red profile actually carries cued ISR doctrine. |
| Hybrid replaces S3's two Commander steps with **one Communicator.send** | The hybrid profile carries zero Commander verbs (irregular forces have no formal staff); the script substitutes informal radio guidance. |
| Co A posture is **DISMOUNTED**, not MOUNTED | Hybrid's `mover.allowed_postures` excludes MOUNTED. DISMOUNTED is in all three profiles. |
| Co B uses **engage**, not suppress | Hybrid's `notional.indirect.improvised` only supports `engage` (peer/near-peer indirect.medium supports engage/suppress/destroy). |

## Uncertainty band exercise

The DoD requires uncertainty bands be exercised. The Co B engage step
does this:

1. Resolve the doctrine's indirect weapon
   (`notional.indirect.medium` for peer/near-peer,
   `notional.indirect.improvised` for hybrid).
2. Read its **nominal** `effective_range_m` from the profile.
3. Read the matching uncertainty band on
   `effector.weapon_systems[<id>].effective_range_m` and compute
   `upper_with_band = nominal × (1 + band_pct)` (or `band_upper` for
   absolute-bound bands).
4. Cap to `effect_parameter_ranges["indirect_fire_arc"]["range_m"].max`
   (the WS-202 validator does not yet implement post-hoc clamping —
   see services/czml-validator/README.md Open Q — so the agent caps
   client-side before emission).
5. Stamp the per-step result with
   `uncertainty_reasoning = {nominal, upper_with_band, chosen, capped,
   band_kind, band_value, profile_cap}`.

For all three doctrines, the cap kicks in:

| Doctrine | Weapon | Nominal | Band | Upper-with-band | Cap | Chosen |
|---|---|---|---|---|---|---|
| `peer` | indirect.medium | 30000 m | ±20% | 36000 m | 30000 m | **30000 m** |
| `near-peer` | indirect.medium | 22000 m | ±30% | 28600 m | 22000 m | **22000 m** |
| `hybrid` | indirect.improvised | 4000 m | ±50% | 6000 m | 4000 m | **4000 m** |

`test_uncertainty_band_exercised_on_engage` asserts both:
- The reasoning was actually recorded (the agent reasoned about the band).
- `chosen == profile_cap < upper_with_band` (the cap kicked in).

## API contract

```python
from almighty_agent_runtime.crews import CrewContext
from almighty_red_crew import run_red_crew

ctx = CrewContext(
    tenant_id="11111111-1111-4111-8111-111111111111",
    scenario_id="22222222-2222-4222-8222-222222222222",
    turn=1,
)
result = run_red_crew(ctx, doctrine="peer")
# CrewResult(crew='red', duration_ms=…, notes='v1 deterministic red crew — doctrine=peer; 10 events committed', metadata={...})
```

`metadata.steps` is a list of `{step, event_id, verb, officer_type,
validator, [uncertainty_reasoning]}`. The Co B engage step is the only
one that carries `uncertainty_reasoning`; the rest are simple commit
records.

## Integration with WS-401 harness

The v1 crew matches Shane's `CrewRunner = Callable[[CrewContext],
CrewResult]` signature and exports `RED_RUNNER`. The WS-401 harness's
`RED_CREWS["default"]` is currently the no-op stub; a follow-up ticket
should swap it once WS-403 (blue) and WS-405 (white cell) are also
ready to land together. The integration form will look like:

```python
# In agents/runtime/src/almighty_agent_runtime/crews.py:
from almighty_red_crew import RED_RUNNER
RED_CREWS["default"] = RED_RUNNER
```

Doctrine selection in the harness will likely use the env var
(set per worker process), since the runtime is process-per-tenant.

## Run

```bash
# From this directory (agents/red/):
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

## Tests — 15 passing

Parameterized over all three doctrines:

- `test_crew_runs_one_full_cycle_per_doctrine` (×3) — DoD; cycle
  completes with zero validator rejections per doctrine.
- `test_uncertainty_band_exercised_on_engage` (×3) — Co B engage step
  carries `uncertainty_reasoning`; `chosen == profile_cap <
  upper_with_band`.
- `test_every_step_has_a_unique_event_id` (×3) — sanity.

Plus six standalone tests:

- `test_step_count_per_doctrine` — 10 / 10 / 9 across peer / near-peer / hybrid.
- `test_default_doctrine_is_peer` — no arg + no env var.
- `test_env_var_overrides_default` — `ALMIGHTY_RED_DOCTRINE=near-peer`.
- `test_explicit_arg_overrides_env_var` — kwarg wins.
- `test_invalid_doctrine_raises` — ValueError on unknown flavor.
- `test_runner_export_is_callable` — `RED_RUNNER` matches WS-401 signature.

Tests use real `NamespacedDag`, real `Validator`, real `OfficerToolBase`
instances. No mocks of upstream contracts — drift surfaces immediately.

## Layout

```
agents/red/
├── pyproject.toml
├── README.md                                        ← this file
├── src/almighty_red_crew/
│   ├── __init__.py                                  ← exports run_red_crew, RED_RUNNER, Doctrine
│   ├── doctrine.py                                  ← east-bank anchors, doctrine flavor blocks
│   ├── profile.py                                   ← load_profile(doctrine) — cached
│   ├── uncertainty.py                               ← resolve_uncertain_value (band → chosen)
│   ├── s2.py / s3.py / s6.py                        ← per-role bases (BASE_GOAL/BASE_BACKSTORY/ALLOWED_VERBS)
│   ├── co_a.py / co_b.py / co_c.py
│   └── crew.py                                      ← run_red_crew(ctx, doctrine), RED_RUNNER, scripts
└── tests/
    ├── conftest.py
    └── test_crew.py
```

## Notes / open questions

- **WS-202 doesn't yet clamp on uncertainty.** The agent caps client-side
  before emission. When WS-202 grows post-hoc clamping (a future
  cross-cutting ticket), the agent can issue the band-stretched value
  directly and let the validator cap. Until then this client-side cap
  is the contract.
- **`destroy` is in companies' allowed set but not called.** Same as
  WS-403 — reserved for the WS-405 adjudicator's `human_required=true`
  flow.
- **No `classify` in the red script.** No red profile authorizes
  `keyhole_footprint`. If a red profile starts to (cued ISR doctrine),
  add the step.
- **No `S2.detect` modality dispatch demonstrated.** Hybrid's narrow
  `effect_parameter_ranges` forces EO_IR, which is the no-validator
  branch. v2 with richer profiles may exercise modality dispatch.

## See also

- [`agents/blue/`](../blue/) — WS-403 sibling.
- [`docs/schema/officer-interfaces.md`](../../docs/schema/officer-interfaces.md) — verb signatures (WS-105).
- [`docs/schema/capability-profiles.md`](../../docs/schema/capability-profiles.md) — uncertainty schema (WS-106 § 6).
- [`kernel/capability-profiles/peer.json`](../../kernel/capability-profiles/peer.json) / [`near-peer.json`](../../kernel/capability-profiles/near-peer.json) / [`hybrid-irregular.json`](../../kernel/capability-profiles/hybrid-irregular.json) — bound profiles (WS-107).
- [`services/czml-validator/`](../../services/czml-validator/) — validator (WS-202).
- WS-405 (#25) — white cell adjudicator agent, sibling.
- WS-601 (#32) — Nashville scenario integration.
