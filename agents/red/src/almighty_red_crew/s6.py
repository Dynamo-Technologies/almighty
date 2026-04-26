"""S6 — Red battalion signal.

Peer red profiles allow `jam`, so this role's ALLOWED_VERBS includes
all four Communicator verbs. In hybrid doctrine the profile may still
omit `jam` (improvised EW); the capability gate handles that at run time.
"""

from __future__ import annotations

from typing import Final

ROLE: Final[str] = "Red S6 (Signal)"

BASE_GOAL: Final[str] = (
    "Maintain comms paths for the assault force. Where the profile "
    "permits, suppress blue's command-and-control by jamming relevant "
    "RF bands over the west-bank objective. Submit reports so higher "
    "echelon (or, in hybrid, the informal command cell) knows the "
    "comms posture."
)

BASE_BACKSTORY: Final[str] = (
    "Your tools are the four Communicator verbs (send, relay, jam, "
    "report). Red doctrine is more aggressive on EW than blue — you "
    "are expected to actively shape blue's comms posture, not just "
    "preserve your own."
)

ALLOWED_VERBS: Final[frozenset[str]] = frozenset(
    {"send", "relay", "jam", "report"}
)
