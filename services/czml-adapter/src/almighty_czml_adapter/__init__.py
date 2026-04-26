"""Almighty live PyRapide -> CZML adapter (WS-503).

Subscribes to a tenant's `events` channel on the WS-304 fan-out
service, translates each spatial-artifact-bearing event into a
post-substitution CZML packet (gated by the WS-202 validator), and
publishes the packet to the tenant's `czml_packets` channel for the
Resium renderer (WS-503 renderer side, owned by Alex).

See README.md for the renderer-side integration contract.
"""

from .models import AdapterResult, EntityPosition, ResultKind
from .translator import translate_event

__all__ = [
    "AdapterResult",
    "EntityPosition",
    "ResultKind",
    "translate_event",
]
