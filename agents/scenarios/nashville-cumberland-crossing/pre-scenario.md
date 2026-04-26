# WS-601 — Pre-scenario runbook (white cell)

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

The operator runbook for the **Nashville Cumberland River crossing**
demo. Performed by a single white-cell operator before turn 1 is
enqueued. Companion files: [`scenario.yaml`](scenario.yaml),
[`assertions.md`](assertions.md).

Estimated duration: **5 minutes** of operator action.

---

## 0. Prerequisites (verify, don't author)

These should already be in place from the upstream WS-NNN PRs. If any
fails, stop — do not work around it.

- [ ] **Tenant exists.** `tenant_id = 00000000-0000-4d00-8000-000000000001`
      visible in the control-plane (WS-301) tenant list.
- [ ] **Scenario row created.** `scenario_id = 00000000-0000-4101-8000-000000000001`
      with `current_turn = 0` and `turn_state = 'open'` (WS-302 schema).
- [ ] **Capability profiles loaded.** Both
      [`us-bct.json`](../../../kernel/capability-profiles/us-bct.json)
      and [`peer.json`](../../../kernel/capability-profiles/peer.json)
      validate against
      [`docs/schema/capability-profile.schema.json`](../../../docs/schema/capability-profile.schema.json)
      (run `kernel/capability-profiles/validate.sh`).
- [ ] **Crews wired.** WS-401 follow-up `register_real_crews()` swap
      landed (PR #68); workers will drive
      `almighty_blue_crew` / `almighty_red_crew` / `almighty_white_cell`.
- [ ] **AAR replay surface live.** WS-506 routes mounted at
      `/:tenantId/scenarios/:scenarioId/aar`.
- [ ] **Per-tenant S3 bucket exists.** `almighty-<tenant_id>-dev`
      reachable from the control-plane's task role (WS-004).

---

## 1. Authoring step (confirm pre-loaded)

Open the white-cell console (WS-505) at:

```
/00000000-0000-4d00-8000-000000000001/scenarios/00000000-0000-4101-8000-000000000001/white-cell
```

In the **Capability profile authoring** panel, confirm the two profiles
are bound to the right entity sets:

| Profile | Bound to |
|---|---|
| `us-bct@1` | All BLUE entities (`type_subtype_ref` matching `notional.ground.bct.*`) |
| `peer@1`   | All RED entities (`type_subtype_ref` matching `notional.peer.*`) |

If both are green, do not edit. Editing a profile after first binding
forks it (per WS-106 § 5) and breaks the AAR provenance for this run.

---

## 2. Override policies (the demo's load-bearing white-cell action)

Three policies, authored in this order. The override gateway (WS-303)
applies them in the priority documented in
[`docs/glossary.md` § 5](../../../docs/glossary.md#5-override-scopes):
**per-event > per-agent-per-turn > per-turn**, default `review`.

### 2a. Per-event review for irreversible Effector verbs

Click **"New override policy"**, fill:

| Field | Value |
|---|---|
| Scope | `per-event` |
| Target predicate | `verb in ["destroy", "disable"]` |
| Action | `review` |
| TTL turns | `6` (lasts the whole scenario) |
| Rationale | "Irreversible effects always pass through human ack." |

This is the **highest-priority policy** in this scenario. Every
`Effector.destroy` and `Effector.disable` event will route to the
white-cell review queue regardless of the per-turn policies below.

### 2b. Per-turn auto-approve for turns 1–3 (warm-up phase)

| Field | Value |
|---|---|
| Scope | `per-turn` |
| Target predicate | `turn in [1, 2, 3]` |
| Action | `auto-approve` |
| TTL turns | `3` |
| Rationale | "Low-risk early scenario phase; auto-commit non-Effector verbs." |

### 2c. Per-turn manual review for turns 4–6 (late phase)

| Field | Value |
|---|---|
| Scope | `per-turn` |
| Target predicate | `turn in [4, 5, 6]` |
| Action | `review` |
| TTL turns | `3` |
| Rationale | "Late phase escalation; everything routes through white cell." |

### Verification

The active-policies table at the top of the white-cell console should
show exactly **three** active rows. Click each to confirm scope, target
predicate, and rationale match.

The expected steady-state behavior across the scenario:

| Turn | Effector.destroy/disable | Other verbs |
|---|---|---|
| 1 | review (per-event wins) | auto-approve |
| 2 | review | auto-approve |
| 3 | review | auto-approve |
| 4 | review | review |
| 5 | review | review |
| 6 | review | review |

---

## 3. Adjudicator readiness

The white-cell adjudicator agent (WS-405) runs after blue and red
crews complete each turn. It produces `proposed_resolution` events with
a `human_required` flag for high-stakes events. Confirm the
**Adjudication surface** panel is empty before kickoff (no leftover
flags from a previous run).

If the panel has leftover entries, the previous scenario didn't reach a
clean termination — investigate before launching this run rather than
clearing them by hand.

---

## 4. Kickoff — enqueue turn 1

Click **"Advance turn"** in the **Turn controls** panel. The button
calls `POST /tenants/:id/scenarios/:sid/turns/advance` (WS-302).

Expected response within ~5 s:

```json
{
  "tenantId":      "00000000-0000-4d00-8000-000000000001",
  "scenarioId":    "00000000-0000-4101-8000-000000000001",
  "closedTurn":    0,
  "newTurn":       1,
  "snapshotId":    "<uuid>",
  "agentRuntimeMs": <int>
}
```

The **Override review queue** panel will populate as the deterministic
crews emit events through the gateway. From here on the demo runs
through the EXCON consoles (WS-504) and the AAR (WS-506), with white
cell intervention at the boundaries listed in §2.

---

## 5. Hand-off

When this runbook is complete:

- Active override policies: 3
- Current turn: 1
- Override review queue: populating
- Adjudication surface: 0 entries (will populate after turn 1 closes)

The blue and red operators (or the deterministic crews driven by the
between-turn harness — pick one model per demo) take it from here.

The white cell operator's remaining job is the **review queue cadence**
listed in [`assertions.md`](assertions.md) §2 — confirm the per-event
destroy/disable policy fires at least once and that the manual-review
turns 4-6 require the operator's ack on every event.
