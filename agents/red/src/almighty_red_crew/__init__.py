"""Almighty red OpFor crew stubs (WS-404).

A red battalion attempting a forced crossing of the Cumberland River.
Six CrewAI agents under a doctrine flavor selectable per scenario:
``peer``, ``near-peer``, or ``hybrid``. Bound to the matching capability
profile from WS-107; uncertainty bands actively exercised in the
deterministic between-turn script.
"""

from .crew import RED_RUNNER, run_red_crew
from .doctrine import DEFAULT_DOCTRINE, Doctrine

__all__ = ["run_red_crew", "RED_RUNNER", "Doctrine", "DEFAULT_DOCTRINE"]
