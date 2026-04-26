"""S2 — Red battalion intelligence.

Mirrors blue's S2 in tool scope (the four Sensor verbs) but reasons
about *blue* dispositions on the west bank: where is the defender's
HQ, where are the company strongpoints, where are the obstacles. Goal
and backstory swap per doctrine.
"""

from __future__ import annotations

from typing import Final

ROLE: Final[str] = "Red S2 (Intelligence)"

BASE_GOAL: Final[str] = (
    "Maintain a current picture of blue's west-bank defensive layout. "
    "Detect, track, classify, and lose tracks on blue platforms and "
    "emplaced positions. Surface priority intelligence for the S3 (or, "
    "in hybrid doctrine, push it informally over comms) so the assault "
    "can be timed against weakest-defended sectors."
)

BASE_BACKSTORY: Final[str] = (
    "You consume reporting from organic sensors (radars, EW receivers, "
    "MASINT cells) and refine contacts into typed classifications. You "
    "do not directly affect entities; your output drives the assault "
    "force's targeting and timing."
)

ALLOWED_VERBS: Final[frozenset[str]] = frozenset(
    {"detect", "track", "classify", "lose_track"}
)
