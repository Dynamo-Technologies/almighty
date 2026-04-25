"""Tenant/scenario-namespaced wrapper around PyRapide's Poset.

The PyRapide ``Poset`` is the underlying causal DAG. The Almighty kernel
partitions it by ``(tenant_id, scenario_id)``: each namespace gets its own
``Poset`` instance, which makes cross-namespace event leakage impossible
by construction (a read can only return events from the namespace's own
Poset; there is no shared store).

Every commit and every read enforces the namespace contract: missing
``tenant_id`` or ``scenario_id`` raises :class:`MissingNamespaceError`.
A predecessor reference to an event from a different namespace raises
:class:`NamespaceMismatchError`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator
from pyrapide import Event as PyRapideEvent
from pyrapide import Poset

from almighty_kernel.errors import MissingNamespaceError, NamespaceMismatchError

OfficerType = Literal[
    "SENSOR",
    "EFFECTOR",
    "MOVER",
    "COMMUNICATOR",
    "COMMANDER",
]


class KernelEvent(BaseModel):
    """Domain event mirroring the WS-101 event schema.

    Field semantics match ``docs/schema/entity-event.md``. Validation here
    is intentionally light (types + non-empty action_verb); the heavy lifts
    — action_verb enumeration (WS-105) and capability gating (WS-202) —
    happen in the layers that wrap this one.
    """

    event_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    scenario_id: UUID
    turn: int = Field(ge=0)
    source_officer_type: OfficerType
    source_entity_id: UUID
    action_verb: str
    payload: dict = Field(default_factory=dict)
    causal_predecessors: list[UUID] = Field(default_factory=list)
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("action_verb")
    @classmethod
    def _action_verb_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("action_verb must be non-empty")
        return v


# Internal sentinel for "namespace key" — keeps the type explicit at call sites.
_NamespaceKey = tuple[UUID, UUID]


def _require_namespace(tenant_id: UUID | None, scenario_id: UUID | None) -> _NamespaceKey:
    """Validate the namespace pair; raise MissingNamespaceError on either missing."""
    missing = []
    if tenant_id is None:
        missing.append("tenant_id")
    if scenario_id is None:
        missing.append("scenario_id")
    if missing:
        raise MissingNamespaceError(
            f"namespace identifiers required but missing: {', '.join(missing)}"
        )
    return (tenant_id, scenario_id)  # type: ignore[return-value]


class NamespacedDag:
    """A causal DAG partitioned by ``(tenant_id, scenario_id)``.

    Each namespace gets its own PyRapide Poset. The wrapper provides:

    - :meth:`commit` — insert an event into its namespace's Poset.
    - :meth:`read` — list events in the namespace, optionally in causal order.
    - :meth:`topological_order` — explicit topological iteration.
    - :meth:`namespaces` — diagnostic; lists all (tenant_id, scenario_id) keys.

    No method accepts events from one namespace and returns them under
    another. The single store is keyed on ``(tenant_id, scenario_id)`` so
    cross-namespace leakage is structurally impossible.
    """

    def __init__(self) -> None:
        self._posets: dict[_NamespaceKey, Poset] = {}
        # event_id → (namespace, pyrapide_event) — used to resolve predecessor
        # references to the underlying Poset events for the add() call. The
        # namespace check on resolution is what enforces NamespaceMismatchError.
        self._index: dict[UUID, tuple[_NamespaceKey, PyRapideEvent]] = {}

    # ------------------------------------------------------------------
    # Namespace management
    # ------------------------------------------------------------------

    def _ensure_poset(self, key: _NamespaceKey) -> Poset:
        poset = self._posets.get(key)
        if poset is None:
            poset = Poset()
            self._posets[key] = poset
        return poset

    def namespaces(self) -> list[_NamespaceKey]:
        """Return the list of namespaces that have at least one event."""
        return list(self._posets.keys())

    def __len__(self) -> int:
        return sum(len(p) for p in self._posets.values())

    # ------------------------------------------------------------------
    # Commit
    # ------------------------------------------------------------------

    def commit(self, event: KernelEvent) -> KernelEvent:
        """Append an event to its namespace's Poset.

        Raises:
            MissingNamespaceError: if ``event.tenant_id`` or ``event.scenario_id``
                is missing. (Pydantic blocks ``None`` at construction time, so
                this is a defense-in-depth check.)
            NamespaceMismatchError: if any ``causal_predecessor`` resolves to an
                event in a different namespace.
            KeyError: if any ``causal_predecessor`` references an unknown event_id.
        """
        key = _require_namespace(event.tenant_id, event.scenario_id)

        # Resolve predecessors. Each must (a) exist and (b) live in the same
        # namespace. We do not silently filter — both failures raise.
        predecessor_events: list[PyRapideEvent] = []
        for pred_id in event.causal_predecessors:
            indexed = self._index.get(pred_id)
            if indexed is None:
                raise KeyError(
                    f"causal_predecessor {pred_id} is unknown to this DAG"
                )
            pred_key, pred_pyrapide = indexed
            if pred_key != key:
                raise NamespaceMismatchError(
                    f"causal_predecessor {pred_id} lives in namespace "
                    f"{pred_key} but the new event targets {key}"
                )
            predecessor_events.append(pred_pyrapide)

        poset = self._ensure_poset(key)
        pyrapide_event = PyRapideEvent(
            name=event.action_verb,
            payload=event.payload,
            source=str(event.source_entity_id),
            metadata={
                "event_id": str(event.event_id),
                "tenant_id": str(event.tenant_id),
                "scenario_id": str(event.scenario_id),
                "turn": event.turn,
                "source_officer_type": event.source_officer_type,
                "source_entity_id": str(event.source_entity_id),
                "ts": event.ts.isoformat(),
            },
        )
        poset.add(pyrapide_event, caused_by=predecessor_events or None)
        self._index[event.event_id] = (key, pyrapide_event)
        return event

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read(
        self,
        *,
        tenant_id: UUID | None = None,
        scenario_id: UUID | None = None,
        causal_order: bool = False,
    ) -> list[KernelEvent]:
        """List the events in a namespace.

        Args:
            tenant_id: required.
            scenario_id: required.
            causal_order: if True, return events in topological (causal)
                order. If False (default), return in insertion order.

        Raises:
            MissingNamespaceError: if either identifier is missing.

        Returns:
            A new list of :class:`KernelEvent`. Empty if the namespace has
            never been committed to.
        """
        key = _require_namespace(tenant_id, scenario_id)
        poset = self._posets.get(key)
        if poset is None:
            return []

        events: Iterable[PyRapideEvent]
        if causal_order:
            events = poset.topological_order()
        else:
            events = poset.events  # readonly property; insertion order

        return [self._reconstruct(e) for e in events]

    def topological_order(
        self,
        *,
        tenant_id: UUID | None = None,
        scenario_id: UUID | None = None,
    ) -> list[KernelEvent]:
        """Convenience: read() with causal_order=True."""
        return self.read(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            causal_order=True,
        )

    # ------------------------------------------------------------------
    # Internal: pyrapide → KernelEvent reconstruction
    # ------------------------------------------------------------------

    @staticmethod
    def _reconstruct(pyrapide_event: PyRapideEvent) -> KernelEvent:
        meta = pyrapide_event.metadata or {}
        return KernelEvent(
            event_id=UUID(meta["event_id"]),
            tenant_id=UUID(meta["tenant_id"]),
            scenario_id=UUID(meta["scenario_id"]),
            turn=int(meta["turn"]),
            source_officer_type=meta["source_officer_type"],
            source_entity_id=UUID(meta["source_entity_id"]),
            action_verb=pyrapide_event.name,
            payload=dict(pyrapide_event.payload or {}),
            causal_predecessors=[],  # not reconstructed; query the DAG instead
            ts=datetime.fromisoformat(meta["ts"]),
        )
