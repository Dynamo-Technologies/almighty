"""Registry helper — instantiate all 20 officer tools for a given context.

WS-403 / WS-404 / WS-405 will typically construct the subset of tools
their crew agents need (e.g., a Sensor-only S2 agent gets only the four
Sensor tools). For tests and for crews that want the full 20-verb
toolbox, ``build_all_tools`` returns a name-keyed dict.
"""

from __future__ import annotations

from .base import OfficerToolBase
from .commander import (
    DelegateTool,
    EscalateTool,
    IssueOrderTool,
    RequestSupportTool,
)
from .communicator import JamTool, RelayTool, ReportTool, SendTool
from .context import OfficerToolContext
from .effector import DestroyTool, DisableTool, EngageTool, SuppressTool
from .mover import AssumePostureTool, FollowRouteTool, HaltTool, MoveToTool
from .sensor import ClassifyTool, DetectTool, LoseTrackTool, TrackTool

ALL_TOOL_CLASSES: list[type[OfficerToolBase]] = [
    # Sensor
    DetectTool,
    TrackTool,
    ClassifyTool,
    LoseTrackTool,
    # Effector
    EngageTool,
    SuppressTool,
    DestroyTool,
    DisableTool,
    # Mover
    MoveToTool,
    FollowRouteTool,
    HaltTool,
    AssumePostureTool,
    # Communicator
    SendTool,
    RelayTool,
    JamTool,
    ReportTool,
    # Commander
    IssueOrderTool,
    RequestSupportTool,
    DelegateTool,
    EscalateTool,
]


def build_all_tools(ctx: OfficerToolContext) -> dict[str, OfficerToolBase]:
    """Instantiate one tool per verb, all bound to ``ctx``.

    Returned dict is keyed on the verb name (e.g. ``"detect"``,
    ``"engage"``) so callers can pluck individual tools by name.
    """
    return {cls.VERB: cls(ctx=ctx) for cls in ALL_TOOL_CLASSES}
