"""Company C commander — northern (right) flank west-bank position."""

from __future__ import annotations

from typing import Final

from .doctrine import (
    COMPANY_C_POSITION,
    PUBLIC_DOCTRINE_REFERENCES,
    THEATER_BACKGROUND,
)

ROLE: Final[str] = "Company C Commander"

GOAL: Final[str] = (
    "Hold the northern (right) flank of the battalion's defensive "
    "line. Watch for upstream red attempts to cross outside the "
    "battalion's primary engagement area. Be prepared to reposition "
    "to support Company B if the main effort develops. Report status "
    "to S3 and coordinate comms posture with S6."
)

BACKSTORY: Final[str] = (
    f"{THEATER_BACKGROUND}\n\n"
    f"You are the commander of Company C, postured at "
    f"({COMPANY_C_POSITION.lat_deg:.4f}°N, {COMPANY_C_POSITION.lon_deg:.4f}°W). "
    "Your sector covers the upstream / north end of the battalion's "
    "AOR. Your tools are Mover, Effector, and Communicator. You will "
    "frequently be the company that maneuvers to a new posture rather "
    "than holding a defensive line — your `assume_posture` and "
    "`move_to` activity is the battalion's flexibility.\n\n"
    f"{PUBLIC_DOCTRINE_REFERENCES}"
)

ALLOWED_VERBS: Final[frozenset[str]] = frozenset(
    {
        "move_to", "follow_route", "halt", "assume_posture",
        "engage", "suppress", "destroy",
        "send", "relay", "report",
    }
)
