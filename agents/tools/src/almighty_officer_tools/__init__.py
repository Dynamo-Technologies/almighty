"""Almighty officer interface tool wrappers (WS-402).

Twenty CrewAI tools, one per officer verb. See README.md for the
integration shape and `docs/schema/officer-interfaces.md` (WS-105) for
the canonical verb contracts.
"""

from .base import OfficerToolBase
from .context import OfficerToolContext, ToolError
from .registry import build_all_tools

__all__ = [
    "OfficerToolBase",
    "OfficerToolContext",
    "ToolError",
    "build_all_tools",
]
