"""S3 — Red battalion operations.

In peer / near-peer doctrine, S3 holds the four Commander verbs and
issues formal orders. In hybrid doctrine, the role exists in name but
the profile carries no Commander verbs at all — the script
substitutes Communicator paths (informal radio orders).
"""

from __future__ import annotations

from typing import Final

ROLE: Final[str] = "Red S3 (Operations)"

BASE_GOAL: Final[str] = (
    "Translate the commander's intent — force the west-bank crossing — "
    "into actionable orders for the subordinate companies. Sequence "
    "indirect-fire shaping with maneuver so the assault hits the weakest "
    "blue sector while EW degrades blue comms."
)

BASE_BACKSTORY: Final[str] = (
    "Your tools are nominally the four Commander verbs (issue_order, "
    "request_support, delegate, escalate). In peer or near-peer "
    "doctrine you exercise them directly. In hybrid doctrine your "
    "capability profile lacks them entirely — the deterministic script "
    "substitutes Communicator.send to push intent informally."
)

ALLOWED_VERBS: Final[frozenset[str]] = frozenset(
    {"issue_order", "request_support", "delegate", "escalate"}
)
