"""Crew abstraction.

The harness owns process lifecycle and queue routing; the *crews* are
the actual decision-making machinery (CrewAI agents in WS-403/404/405).

For WS-401 we ship a :class:`NoOpCrew` placeholder per side so the
harness can run end-to-end before the real crews land. WS-403 (#23) and
WS-404 (#24) replace ``BLUE_CREWS`` and ``RED_CREWS`` with CrewAI
:class:`crewai.Crew` instances; WS-405 (#25) replaces ``WHITE_CREWS``
with the adjudicator.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Literal

CrewName = Literal["blue", "red", "white"]


@dataclass
class CrewResult:
    """Return shape from a crew run.

    Kept narrow on purpose. The harness only cares whether the crew
    finished and any high-level metadata; per-event detail goes through
    the kernel commit path (WS-104) and the override gateway (WS-303).
    """

    crew: CrewName
    duration_ms: int
    notes: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class CrewContext:
    """Inputs every crew receives at run time."""

    tenant_id: str
    scenario_id: str
    turn: int


CrewRunner = Callable[[CrewContext], CrewResult]


# ---------------------------------------------------------------------------
# v1 stub crews — replaced by WS-403 / WS-404 / WS-405.
# ---------------------------------------------------------------------------


def _noop_crew_runner(crew: CrewName) -> CrewRunner:
    def _run(ctx: CrewContext) -> CrewResult:
        started = time.perf_counter()
        # Keep this fast — the empty-crew DoD requires < 2 s end-to-end.
        time.sleep(0.0)
        ms = int((time.perf_counter() - started) * 1000)
        return CrewResult(
            crew=crew,
            duration_ms=ms,
            notes="noop crew (WS-401 stub)",
            metadata={"tenant_id": ctx.tenant_id, "scenario_id": ctx.scenario_id, "turn": ctx.turn},
        )

    return _run


# Crew registries. WS-403/404/405 swap these out.
BLUE_CREWS: dict[str, CrewRunner] = {"default": _noop_crew_runner("blue")}
RED_CREWS: dict[str, CrewRunner] = {"default": _noop_crew_runner("red")}
WHITE_CREWS: dict[str, CrewRunner] = {"default": _noop_crew_runner("white")}


def get_crew_runner(crew: CrewName) -> CrewRunner:
    """Return the runner for the named side. Picks the ``"default"``
    profile until WS-403/404/405 introduces variants."""
    if crew == "blue":
        return BLUE_CREWS["default"]
    if crew == "red":
        return RED_CREWS["default"]
    if crew == "white":
        return WHITE_CREWS["default"]
    raise ValueError(f"unknown crew: {crew!r}")
