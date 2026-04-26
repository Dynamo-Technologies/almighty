"""Stake classification.

Per the WS-405 runbook: implement ``stake_level(event) -> 'low' |
'medium' | 'high'`` and let callers override the heuristic for
scenario-specific policy. The high-stakes path is the contract — the
adjudicator holds these for human ack regardless of how the rest of
the heuristic moves.

WS-101's entity schema does not yet carry a ``population_center`` /
``civilian`` flag (an open question I flagged in the WS-108 review).
v1 therefore can't gate on "destroy on a population center" the way
the runbook hints; instead we surface the runbook's intent through
inputs the call site CAN provide:

  - Verbs WS-105 marks as adjudication-flagged (`destroy` always;
    `engage` / `disable` / `jam` optionally) escalate to high when
    the event payload signals it (`stake='high'`, neutral target,
    civilian-band overlap).
  - Callers can supply a custom :class:`StakePredicate` via the
    adjudicator constructor for scenario-specific rules (e.g., the
    Nashville WS-601 scenario will mark certain coordinates as
    population centers).

The default predicate aims to be conservative — when in doubt,
escalate. The white cell would rather sit through a few extra
auto-approvable reviews than auto-commit something that should have
been held.
"""

from __future__ import annotations

from typing import Callable, Literal

from almighty_kernel.dag import KernelEvent

StakeLevel = Literal["low", "medium", "high"]
StakePredicate = Callable[[KernelEvent], StakeLevel]


# WS-105 § Summary marks these verbs as adjudication-flagged.
_ALWAYS_HIGH_VERBS = frozenset({"destroy"})
_OPTIONALLY_HIGH_VERBS = frozenset({"engage", "disable", "jam"})
_MEDIUM_VERBS = frozenset({"engage", "suppress", "jam", "disable"})


def _payload_has_high_marker(event: KernelEvent) -> bool:
    """The WS-402 destroy tool stamps ``payload.stake = 'high'``. Other
    tools may set this in v2. Respect the stamp regardless of verb."""
    return event.payload.get("stake") == "high"


def _payload_targets_neutral(event: KernelEvent) -> bool:
    """Caller-annotated neutral target. v1 has no global entity
    affiliation lookup, so the call site annotates the payload."""
    return event.payload.get("target_force_affiliation") == "NEUTRAL"


def _payload_targets_civilian(event: KernelEvent) -> bool:
    """Caller-annotated civilian target / area / band."""
    return bool(
        event.payload.get("target_is_civilian")
        or event.payload.get("civilian_band_overlap")
        or event.payload.get("population_center", False)
    )


def stake_level(event: KernelEvent) -> StakeLevel:
    """Default stake heuristic. Override by passing a custom
    :class:`StakePredicate` to :func:`adjudicate_events`."""
    verb = event.action_verb

    # Hard-floor on the always-high verbs.
    if verb in _ALWAYS_HIGH_VERBS:
        return "high"

    # Explicit high-stakes marker stamped by the emitter.
    if _payload_has_high_marker(event):
        return "high"

    # Optionally-high verbs escalate when the target / area is sensitive.
    if verb in _OPTIONALLY_HIGH_VERBS and (
        _payload_targets_neutral(event) or _payload_targets_civilian(event)
    ):
        return "high"

    # Effector + EW area effects without sensitive-target signals.
    if verb in _MEDIUM_VERBS:
        return "medium"

    # Sensor reads, Mover position changes, Communicator messages,
    # Commander orders / requests / delegations / escalations.
    return "low"
