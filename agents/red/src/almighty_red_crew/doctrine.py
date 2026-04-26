"""Doctrine flavor selection + east-bank geography for the red crew.

Three doctrines per the runbook (WS-404):

  peer        — state-aligned conventional opposing force, sophisticated
                EW, balanced uncertainty.
  near-peer   — capable but constrained, more reliance on improvised EW,
                broader uncertainty bands.
  hybrid      — irregular force, no formal staff, very large uncertainty
                on improvised systems. Lacks Commander verbs entirely.

Selection priority at run time:

  1. Explicit ``doctrine`` arg passed to ``run_red_crew(...)``.
  2. ``ALMIGHTY_RED_DOCTRINE`` environment variable.
  3. ``DEFAULT_DOCTRINE`` (``"peer"``).

Public unclassified references for doctrinal flavor language:
  ATP 2-01.3 (Intelligence Preparation of the Battlefield),
  TC 7-100.2 (Opposing Force Tactics),
  TC 7-100.3 (Irregular Opposing Forces).
No specific real-world unit, organization, or weapon system is named.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final, Literal

Doctrine = Literal["peer", "near-peer", "hybrid"]

VALID_DOCTRINES: Final[tuple[Doctrine, ...]] = ("peer", "near-peer", "hybrid")
DEFAULT_DOCTRINE: Final[Doctrine] = "peer"


def select_doctrine(arg: Doctrine | None = None) -> Doctrine:
    """Resolve the doctrine for this crew run.

    Priority: explicit arg > env var > default.
    Raises ``ValueError`` on an invalid value at any source.
    """
    candidate: str | None = arg or os.environ.get("ALMIGHTY_RED_DOCTRINE")
    if candidate is None:
        return DEFAULT_DOCTRINE
    if candidate not in VALID_DOCTRINES:
        raise ValueError(
            f"invalid doctrine {candidate!r}; must be one of {VALID_DOCTRINES}"
        )
    return candidate  # type: ignore[return-value]


# ---- East-bank geography (red attacker positions) ---------------------------
#
# Inverted from the blue defender layout — red is east of the river,
# attacking westward across the crossing.


@dataclass(frozen=True)
class NamedPoint:
    name: str
    lat_deg: float
    lon_deg: float
    alt_m: float


EAST_BANK_BN_HQ = NamedPoint(
    name="RED-BN-HQ-1", lat_deg=36.1750, lon_deg=-86.7600, alt_m=160.0
)
RED_OBSERVATION_POST = NamedPoint(
    name="RED-OP-1", lat_deg=36.1820, lon_deg=-86.7640, alt_m=175.0
)
RED_COMPANY_A_POSITION = NamedPoint(
    name="RED-CO-A-1", lat_deg=36.1700, lon_deg=-86.7550, alt_m=160.0
)
RED_COMPANY_B_POSITION = NamedPoint(
    name="RED-CO-B-1", lat_deg=36.1780, lon_deg=-86.7600, alt_m=162.0
)
RED_COMPANY_C_POSITION = NamedPoint(
    name="RED-CO-C-1", lat_deg=36.1860, lon_deg=-86.7640, alt_m=165.0
)
WEST_BANK_OBJECTIVE_AREA = NamedPoint(
    name="OBJ-WEST-CROSSING", lat_deg=36.1810, lon_deg=-86.7860, alt_m=170.0
)


# ---- Per-doctrine flavor blocks ---------------------------------------------
#
# Each role's GOAL/BACKSTORY is assembled at run time as:
#
#   THEATER_PRELUDE[doctrine]
#   + role.BASE_GOAL / role.BASE_BACKSTORY
#   + DOCTRINE_CAVEAT[doctrine]
#
# This keeps each role file short and centralizes doctrine-specific
# flavor.


THEATER_PRELUDE: Final[dict[Doctrine, str]] = {
    "peer": (
        "You are part of a peer-class opposing-force battalion postured "
        "on the east bank of the Cumberland River north of Nashville. "
        "Your force is a conventional combined-arms element with "
        "sophisticated electronic warfare and indirect-fire capability. "
        "Your task: cross the river and seize the west-bank crossing "
        "objective. The defending blue battalion is dug in; you must "
        "shape the engagement, suppress the defense, and force the "
        "crossing."
    ),
    "near-peer": (
        "You are part of a near-peer opposing-force battalion postured "
        "on the east bank of the Cumberland River. Your force has "
        "conventional indirect fires and tactical EW but is constrained "
        "in ammunition and high-end systems compared to a peer adversary. "
        "Improvise where required. Your task: shape and force the "
        "west-bank crossing despite the resource gap."
    ),
    "hybrid": (
        "You are part of an irregular hybrid force operating on the "
        "east bank of the Cumberland River. There is no formal "
        "battalion staff; orders flow informally over open comms or "
        "courier. Indirect fires are improvised, EW is light and "
        "unreliable, and the operation depends on speed and surprise "
        "rather than firepower. Your task: cross the river by stealth "
        "and infiltrate west-bank positions before the defender "
        "consolidates."
    ),
}

DOCTRINE_CAVEAT: Final[dict[Doctrine, str]] = {
    "peer": (
        "Doctrine reference: TC 7-100.2 (Opposing Force Tactics). "
        "Your capability profile carries uncertainty bands on selected "
        "fields (effector range, sensor range, jamming power). When "
        "reasoning about reach, work the upper edge of the band; the "
        "validator caps emission at the profile's posted maximum."
    ),
    "near-peer": (
        "Doctrine reference: TC 7-100.2 (Opposing Force Tactics) with "
        "near-peer modifiers. Uncertainty bands are wider than a peer "
        "force; expect the validator to clamp aggressive reach claims."
    ),
    "hybrid": (
        "Doctrine reference: TC 7-100.3 (Irregular Opposing Forces). "
        "Your capability profile lacks the four Commander verbs "
        "(issue_order, request_support, delegate, escalate) — irregular "
        "forces have no formal staff structure. The S3 role exists "
        "informally; the deterministic script substitutes Communicator "
        "verbs where a peer S3 would issue formal orders. Uncertainty "
        "bands on improvised systems are very wide."
    ),
}


def assemble_goal(base_goal: str, doctrine: Doctrine) -> str:
    """Combine a role's base goal with doctrine prelude."""
    return f"{THEATER_PRELUDE[doctrine]}\n\n{base_goal}"


def assemble_backstory(base_backstory: str, doctrine: Doctrine) -> str:
    """Combine a role's base backstory with the doctrine caveat."""
    return f"{base_backstory}\n\n{DOCTRINE_CAVEAT[doctrine]}"
