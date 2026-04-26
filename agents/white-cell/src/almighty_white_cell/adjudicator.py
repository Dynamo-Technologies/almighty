"""Adjudicator core.

Reads a turn's worth of pending events, computes per-event stake and
contested-ness, and proposes one :class:`Decision` per event.

A Decision maps onto the WS-303 override-gateway outcome enum:

  high          -> outcome='review-pending', human_required=True
  low / medium  -> outcome='auto-approve',  human_required=False

In v1 the adjudicator does NOT POST to the control-plane HTTP service
(WS-303). Returning Decisions and letting the caller wire them to the
gateway is the v1 contract; HTTP integration is a follow-up.

Contested events get one Decision with ``contested=True`` and a
rationale that names the conflicting event(s). The runbook's
"propose a single proposed_resolution per contested effect" is honored
by yielding exactly one Decision per source event regardless of how
many other events it conflicts with.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal
from uuid import UUID

from almighty_kernel.dag import KernelEvent

from .stakes import StakeLevel, StakePredicate, stake_level

DecisionOutcome = Literal["auto-approve", "review-pending"]
ContestedPredicate = Callable[[KernelEvent, list[KernelEvent]], bool]


@dataclass(frozen=True)
class Decision:
    """One adjudicator-proposed outcome for one event.

    Maps onto a row the WS-303 override gateway would write into
    ``override_decisions`` (see services/control-plane/migrations/
    1763676000003_override-policies.sql).
    """

    event_id: UUID
    action_verb: str
    source_officer_type: str
    stake: StakeLevel
    outcome: DecisionOutcome
    human_required: bool
    contested: bool
    rationale: str
    conflicts_with: list[UUID] = field(default_factory=list)


# ---- Default contested predicate ---------------------------------------------


def _default_contested_predicate(
    event: KernelEvent, all_events: list[KernelEvent]
) -> bool:
    """Default v1 heuristic. An event is contested when:

      (a) its payload carries an explicit ``contested = True`` marker, OR
      (b) its payload's ``adjudication_state == 'contested'`` (per
          WS-108 § 2 enum), OR
      (c) another event in the same batch targets the same
          ``target_entity_id`` from the same turn.

    (c) catches the canonical case the runbook calls out — "did the EW
    cone actually degrade comms?" — by detecting overlapping claims on
    the same target.
    """
    if event.payload.get("contested") is True:
        return True
    if event.payload.get("adjudication_state") == "contested":
        return True
    target = event.payload.get("target_entity_id")
    if not target:
        return False
    for other in all_events:
        if other.event_id == event.event_id:
            continue
        if other.payload.get("target_entity_id") == target and other.turn == event.turn:
            return True
    return False


def _conflicts_for(
    event: KernelEvent, all_events: list[KernelEvent]
) -> list[UUID]:
    """List the event_ids that conflict with this one (same target,
    same turn). Used to populate ``Decision.conflicts_with`` so AAR can
    render the contested set."""
    target = event.payload.get("target_entity_id")
    if not target:
        return []
    return [
        other.event_id
        for other in all_events
        if other.event_id != event.event_id
        and other.payload.get("target_entity_id") == target
        and other.turn == event.turn
    ]


# ---- Public entry point ------------------------------------------------------


def adjudicate_events(
    events: list[KernelEvent],
    *,
    stake_predicate: StakePredicate | None = None,
    contested_predicate: ContestedPredicate | None = None,
) -> list[Decision]:
    """Return one Decision per event, in the order events were given.

    Args:
        events: pending events from this turn (typically the union of
            blue and red crew commits).
        stake_predicate: override the default stake heuristic. The
            high-stakes path is the contract; even a custom predicate
            should not downgrade an obviously-high event without a
            clear scenario reason.
        contested_predicate: override the default contested detection.
    """
    stake_fn = stake_predicate or stake_level
    contested_fn = contested_predicate or _default_contested_predicate

    decisions: list[Decision] = []
    for event in events:
        stake: StakeLevel = stake_fn(event)
        contested = contested_fn(event, events)
        if stake == "high":
            outcome: DecisionOutcome = "review-pending"
            human_required = True
            rationale = _high_stakes_rationale(event, contested)
        else:
            outcome = "auto-approve"
            human_required = False
            rationale = _low_or_medium_rationale(event, stake, contested)
        decisions.append(
            Decision(
                event_id=event.event_id,
                action_verb=event.action_verb,
                source_officer_type=event.source_officer_type,
                stake=stake,
                outcome=outcome,
                human_required=human_required,
                contested=contested,
                rationale=rationale,
                conflicts_with=_conflicts_for(event, events),
            )
        )
    return decisions


# ---- Rationale builders ------------------------------------------------------


def _high_stakes_rationale(event: KernelEvent, contested: bool) -> str:
    parts: list[str] = [
        f"high-stakes verb '{event.action_verb}' from {event.source_officer_type}",
    ]
    if event.payload.get("stake") == "high":
        parts.append("emitter stamped payload.stake='high'")
    if event.payload.get("target_force_affiliation") == "NEUTRAL":
        parts.append("target is NEUTRAL force")
    if event.payload.get("target_is_civilian") or event.payload.get("population_center"):
        parts.append("target is civilian / population center")
    if event.payload.get("civilian_band_overlap"):
        parts.append("EW band overlaps declared civilian frequency")
    if contested:
        parts.append("contested with other events in the same turn")
    parts.append("holding for human ack via WS-303 review-pending state")
    return "; ".join(parts)


def _low_or_medium_rationale(
    event: KernelEvent, stake: StakeLevel, contested: bool
) -> str:
    parts = [f"{stake}-stakes verb '{event.action_verb}'"]
    if contested:
        parts.append("contested but not high-stakes; auto-approving with audit")
    else:
        parts.append("routine path")
    return "; ".join(parts)
