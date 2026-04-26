"""Almighty white-cell adjudicator agent (WS-405).

A single agent that runs after blue and red crews complete, reads the
turn's pending events, computes a stake level per event, and proposes
a resolution:

  high stakes   -> outcome='review-pending', human_required=True
                   (the override gateway holds the event until a white
                    cell operator clicks through via WS-505)
  low / medium  -> outcome='auto-approve', human_required=False
                   (the override gateway commits with the proposed
                    rationale stamped on the audit row)

See README.md for the v1 stake heuristic and the contract with the
WS-303 override gateway.
"""

from .adjudicator import Decision, adjudicate_events
from .crew import WHITE_RUNNER, run_white_crew
from .stakes import StakeLevel, StakePredicate, stake_level

__all__ = [
    "Decision",
    "adjudicate_events",
    "stake_level",
    "StakeLevel",
    "StakePredicate",
    "run_white_crew",
    "WHITE_RUNNER",
]
