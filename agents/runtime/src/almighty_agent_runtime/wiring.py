"""Crew runner wiring.

This module connects the three crew packages (``almighty_blue_crew``,
``almighty_red_crew``, ``almighty_white_cell``) into the harness's
:data:`crews.BLUE_CREWS` / :data:`crews.RED_CREWS` / :data:`crews.WHITE_CREWS`
slots. The harness keeps no-op stubs as the default fallback so the
runtime can be installed and tested in isolation; calling
:func:`register_real_crews` at process startup swaps each side's
``"default"`` slot to the real deterministic runner shipped by
WS-403/WS-404/WS-405.

Each import is guarded so a partial install (e.g., runtime + tools only)
doesn't blow up — sides whose package isn't on the import path stay on
their no-op stub. :func:`register_real_crews` returns the set of sides
that were successfully wired so callers can verify or log.
"""

from __future__ import annotations

import importlib
import logging
from typing import Set

from almighty_agent_runtime import crews

LOG = logging.getLogger(__name__)


def register_real_crews() -> Set[str]:
    """Register the deterministic v1 runners shipped by WS-403/404/405.

    Safe to call multiple times — repeats are idempotent.

    Returns:
        The set of crew names (subset of ``{"blue", "red", "white"}``) that
        were swapped to real runners on this call. Sides whose package
        could not be imported keep their existing (typically no-op) entry.
    """
    wired: Set[str] = set()

    if _try_register_blue():
        wired.add("blue")
    if _try_register_red():
        wired.add("red")
    if _try_register_white():
        wired.add("white")

    if wired:
        LOG.info("registered real crews: %s", ", ".join(sorted(wired)))
    if len(wired) < 3:
        missing = {"blue", "red", "white"} - wired
        LOG.warning(
            "no-op fallback retained for: %s (package not installed)",
            ", ".join(sorted(missing)),
        )
    return wired


def register_noop_crews() -> None:
    """Reset all three slots to no-op stubs.

    Mostly useful in tests that want to undo a previous
    ``register_real_crews()`` call. Production code should not need this.
    """
    # Re-import the module-level stubs by reaching into the factory used
    # at import time. Simpler: just rebuild via the same private helper.
    from almighty_agent_runtime.crews import _noop_crew_runner

    crews.BLUE_CREWS["default"] = _noop_crew_runner("blue")
    crews.RED_CREWS["default"] = _noop_crew_runner("red")
    crews.WHITE_CREWS["default"] = _noop_crew_runner("white")


# ---------------------------------------------------------------------------
# Per-side guarded imports
# ---------------------------------------------------------------------------


def _try_register_blue() -> bool:
    try:
        module = importlib.import_module("almighty_blue_crew")
    except ImportError as exc:
        LOG.debug("almighty_blue_crew not importable: %s", exc)
        return False
    runner = getattr(module, "BLUE_RUNNER", None)
    if runner is None:
        LOG.warning("almighty_blue_crew imported but BLUE_RUNNER missing")
        return False
    crews.BLUE_CREWS["default"] = runner
    return True


def _try_register_red() -> bool:
    try:
        module = importlib.import_module("almighty_red_crew")
    except ImportError as exc:
        LOG.debug("almighty_red_crew not importable: %s", exc)
        return False
    runner = getattr(module, "RED_RUNNER", None)
    if runner is None:
        LOG.warning("almighty_red_crew imported but RED_RUNNER missing")
        return False
    crews.RED_CREWS["default"] = runner
    return True


def _try_register_white() -> bool:
    try:
        module = importlib.import_module("almighty_white_cell")
    except ImportError as exc:
        LOG.debug("almighty_white_cell not importable: %s", exc)
        return False
    runner = getattr(module, "WHITE_RUNNER", None)
    if runner is None:
        LOG.warning("almighty_white_cell imported but WHITE_RUNNER missing")
        return False
    crews.WHITE_CREWS["default"] = runner
    return True
