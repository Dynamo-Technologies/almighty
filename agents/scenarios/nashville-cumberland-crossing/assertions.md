# WS-601 — Assertions checklist

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

Observable conditions that constitute a **successful** demo run of the
Nashville Cumberland River crossing scenario. Confirmed end-of-run by
the white-cell operator (or whoever is recording the demo).

Companion files: [`scenario.yaml`](scenario.yaml),
[`pre-scenario.md`](pre-scenario.md).

`tenant_id = 00000000-0000-4d00-8000-000000000001`,
`scenario_id = 00000000-0000-4101-8000-000000000001`.

---

## 1. Scenario runs to completion across multiple turns

**Pass condition.** `scenarios.current_turn = 6` and
`scenarios.turn_state = 'open'` (or `'closed'` if WS-302 starts emitting
the closed terminal state) at run end.

**Verify** (psql against the tenant's RDS via the control-plane bastion):

```sql
SELECT current_turn, turn_state
  FROM scenarios
 WHERE tenant_id   = '00000000-0000-4d00-8000-000000000001'
   AND scenario_id = '00000000-0000-4101-8000-000000000001';
-- expect: 6 | open
```

And one snapshot per closed turn:

```sql
SELECT turn, count(*) AS n
  FROM turn_snapshots
 WHERE tenant_id   = '00000000-0000-4d00-8000-000000000001'
   AND scenario_id = '00000000-0000-4101-8000-000000000001'
 GROUP BY turn
 ORDER BY turn;
-- expect six rows, turn = 0..5, n = 1 each
```

---

## 2. At least one human override decision recorded

**Pass condition.** The override gateway (WS-303) recorded a
`override_decision` event with `decided_by` set to a human operator
identity (not `auto-approve` / `auto-block` system tags).

The pre-scenario per-event policy on `verb in ["destroy", "disable"]`
guarantees this fires whenever a destroy / disable verb is emitted.
Manual-review turns 4–6 add additional opportunities even if no
destroy / disable events occurred.

**Verify**:

```sql
SELECT count(*) AS human_decisions
  FROM events
 WHERE tenant_id   = '00000000-0000-4d00-8000-000000000001'
   AND scenario_id = '00000000-0000-4101-8000-000000000001'
   AND action_verb = 'override_decision'
   AND payload->>'decision_source' = 'human';
-- expect: >= 1
```

> **Known coverage caveat.** The current deterministic blue crew (WS-403)
> does NOT emit `destroy` or `disable` verbs in its scripted between-turn
> sequence — only `suppress`. The current red crew (WS-404, peer doctrine)
> emits `engage` (with uncertainty) but not `destroy` or `disable`
> either. So the per-event review policy from `pre-scenario.md` § 2a
> may **not actually fire today**.
>
> Closure paths for this assertion:
>
> 1. **Operator drives a destroy via the EXCON console** (WS-504) —
>    the human-driven path is what actually triggers a destroy in v1.
>    Demo recording should plan for this on turn 4 or 5.
> 2. **Manual-review turns 4–6** generate `human` decisions on every
>    routine event, which also satisfies this assertion (the per-turn
>    review policy fires on every blue+red verb in the late phase,
>    independent of destroy/disable).
>
> Treat path 2 as the default safety net. If this assertion fails,
> re-check that policy 2c is active and that turn 4 actually advanced.

---

## 3. Adjudicator (WS-405) flagged at least one high-stakes event

**Pass condition.** The white-cell adjudicator emitted a
`proposed_resolution` event with `human_required = true` for at least
one event during the scenario.

**Verify**:

```sql
SELECT count(*) AS high_stakes_flags
  FROM events
 WHERE tenant_id   = '00000000-0000-4d00-8000-000000000001'
   AND scenario_id = '00000000-0000-4101-8000-000000000001'
   AND action_verb = 'proposed_resolution'
   AND payload->>'human_required' = 'true';
-- expect: >= 1
```

> **Known coverage caveat.** Same as §2: the adjudicator's stake
> heuristic (`agents/white-cell/.../stakes.py`) primarily flags
> `destroy` / `disable` events, which the current crew scripts don't
> emit. To force a flag, the demo recording should include a
> human-driven destroy via the EXCON console on turn 4 or 5.

---

## 4. Final AAR (WS-506) exports to S3 successfully

**Pass condition.** After clicking "Export AAR" in the WS-506 surface,
the per-tenant S3 bucket
`almighty-00000000-0000-4d00-8000-000000000001-dev` contains the four
expected artifacts at
`aar/00000000-0000-4101-8000-000000000001/`.

**Verify**:

```bash
aws s3 ls --recursive \
  s3://almighty-00000000-0000-4d00-8000-000000000001-dev/aar/00000000-0000-4101-8000-000000000001/
# expect (sizes will vary):
#   events.json
#   czml-stream.czml
#   override-decisions.json
#   summary.pdf
```

Spot-checks:

| Artifact | What to check |
|---|---|
| `events.json` | Top-level array; one entry per event in the scenario; ordered by `ts` ascending. |
| `czml-stream.czml` | Valid CZML JSON; `document` packet has `name` referencing the scenario; banner classification line in description. |
| `override-decisions.json` | Per-event log; entries for both auto-approve and review-required outcomes. |
| `summary.pdf` | First page carries the unclassified banner (top + bottom, `#C0DD97`). |

---

## 5. All nine effect families exercised at least once across the scenario

**Pass condition.** Across the six turns, every spatial effect family
listed in [`docs/glossary.md` § 2](../../../docs/glossary.md#2-effect-families)
appears in at least one CZML packet.

The nine families:

```
ew_cone, uas_corridor, radar_fan, jamming_circle, satellite_swath,
indirect_fire_arc, ir_plume, masint_cell, keyhole_footprint
```

**Verify** by reading the per-event `payload` shapes from the events
table (every emit-spatial verb stamps the resolved family on its
payload):

```sql
SELECT DISTINCT payload->>'czml_template' AS family
  FROM events
 WHERE tenant_id   = '00000000-0000-4d00-8000-000000000001'
   AND scenario_id = '00000000-0000-4101-8000-000000000001'
   AND payload ? 'czml_template'
 ORDER BY family;
-- expect: 9 distinct rows covering every family above
```

> **HONEST GAP.** The current deterministic crew scripts (blue + red,
> peer doctrine) only emit **3 of the 9** spatial families when run
> end-to-end:
>
> | Family | Source | Status |
> |---|---|---|
> | `radar_fan` | blue S2 detect (modality=RADAR) | ✅ |
> | `keyhole_footprint` | blue S2 classify | ✅ |
> | `indirect_fire_arc` | blue CO B suppress, red CO B engage | ✅ |
> | `ew_cone` | not exercised | ❌ |
> | `uas_corridor` | not exercised | ❌ |
> | `jamming_circle` | not exercised | ❌ |
> | `satellite_swath` | not exercised | ❌ |
> | `ir_plume` | not exercised (would follow a destroy) | ❌ |
> | `masint_cell` | not exercised | ❌ |
>
> The 6-family gap is real and tracked. Three closure paths, ranked:
>
> 1. **Operator-driven verbs via EXCON consoles** (WS-504). A blue or
>    red operator manually issues `jam`, `relay` (with airborne corridor
>    advertise), and `disable` in turns 4–5; an `ir_plume` can be
>    forced by a human-driven `destroy` (which also satisfies §2 and
>    §3 above). This is the v1 demo answer.
>
> 2. **Augment the deterministic scripts** (WS-403/404 follow-up).
>    Add `_step_s2_detect_ew` (modality=RF or MASINT_MULTI),
>    `_step_co_a_relay_corridor`, `_step_red_jam_crossing` to the
>    scripts so the families fire without operator input. Cleaner for
>    automated regression but it's modifying closed-PR work.
>
> 3. **Static CZML overlay during the demo.** The WS-204 vignette
>    (`czml/demos/nashville-vignette.czml`) already exercises all 9
>    families statically. Loading it as a parallel data source during
>    the demo would visually satisfy the assertion but doesn't actually
>    exercise the live event chain — flagged as cosmetic-only.
>
> The recommended demo recording uses path 1 (operator-driven) on
> turns 4–5 plus the live deterministic crews. If even one family is
> missing at scenario end, this assertion FAILS — record the gap in
> the demo's after-action notes for follow-up.

---

## Summary cheat-sheet

| # | Assertion | Pass = |
|---|---|---|
| 1 | Scenario completes 6 turns | `current_turn = 6` AND 6 snapshot rows |
| 2 | ≥ 1 human override decision | manual-review turns 4–6 OR operator-driven destroy |
| 3 | ≥ 1 adjudicator high-stakes flag | requires destroy / disable in the run (§2 path 1) |
| 4 | AAR exports to S3 | 4 artifacts present at expected prefix |
| 5 | All 9 effect families exercised | requires operator-driven jam / relay / disable / destroy |

**Three of these (§2, §3, §5) currently depend on the human operator
exercising EXCON to fill the deterministic-script gap.** Plan the demo
recording around that — turns 1–3 are crew-driven warm-up, turns 4–5
include operator action to close the gap, turn 6 is wrap-up + AAR export.
