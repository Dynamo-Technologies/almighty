"""Almighty blue battalion crew stubs (WS-403).

A US BCT defending the Cumberland River west bank. Six CrewAI agents:

  S2 (intelligence)  → S3 (operations)  → companies A/B/C  → S6 (signal)

Sequenced as a between-turn process. The v1 crew is deterministic — see
README.md for the rationale and the v2 LLM-driven path.
"""

from .crew import BLUE_RUNNER, run_blue_crew

__all__ = ["run_blue_crew", "BLUE_RUNNER"]
