"""Build a textual situation report from the namespaced PyRapide DAG.

Spec §6a — the "PyRapide → agent" half of the demo's load-bearing edit.
Before an LLM-driven role calls Crew.kickoff(), we pull the topological
order of events from the namespace and format them as a terse text
block the model reasons over.

Pairs with `OfficerToolContext.causal_predecessors` — the calling code
should set that field to the event ids contained in the report so the
resulting commit's `causal_predecessors` cite the precise events the
LLM saw. See spec §6b.
"""

from __future__ import annotations

from uuid import UUID

from almighty_kernel.dag import KernelEvent, NamespacedDag


def build_situation_report(
    dag: NamespacedDag,
    *,
    tenant_id: UUID,
    scenario_id: UUID,
) -> str:
    """Return a one-event-per-line text rendering of the namespace's DAG
    in topological order, suitable for embedding in an LLM task prompt."""
    events = dag.read(tenant_id=tenant_id, scenario_id=scenario_id, causal_order=True)
    if not events:
        return ""
    return "\n".join(_format_event(e) for e in events)


def predecessor_event_ids(
    dag: NamespacedDag,
    *,
    tenant_id: UUID,
    scenario_id: UUID,
) -> list[UUID]:
    """Return the event ids in the namespace, topological order. The caller
    stashes this list on OfficerToolContext.causal_predecessors so the next
    tool commit auto-links to all of them. Spec §6b."""
    return [
        e.event_id
        for e in dag.read(tenant_id=tenant_id, scenario_id=scenario_id, causal_order=True)
    ]


def _format_event(e: KernelEvent) -> str:
    summary = _summarize_payload(e.payload, e.action_verb)
    return (
        f"- [{e.event_id}] turn {e.turn} "
        f"{e.source_officer_type} {e.action_verb}: {summary}"
    )


def _summarize_payload(payload: dict, verb: str) -> str:
    """One-line summary of an event payload for LLM consumption.

    Keeps the situation report compact even with hundreds of events."""
    if not payload:
        return "(no payload)"
    if verb == "detect":
        return (
            f"target={payload.get('target_entity_id', '?')}, "
            f"modality={payload.get('modality', '?')}, "
            f"confidence={payload.get('confidence', '?')}"
        )
    if verb == "classify":
        return (
            f"track={payload.get('track_id', '?')}, "
            f"label={payload.get('classification_label', '?')}, "
            f"confidence={payload.get('confidence', '?')}"
        )
    if verb == "issue_order":
        return (
            f"order_type={payload.get('order_type', '?')}, "
            f"to={payload.get('to_entity_id', '?')}"
        )
    if verb == "suppress":
        return (
            f"target=({payload.get('target_lat_deg', '?')}, "
            f"{payload.get('target_lon_deg', '?')}), "
            f"weapon={payload.get('weapon_system', '?')}"
        )
    keys = list(payload.keys())[:3]
    return ", ".join(f"{k}={payload[k]}" for k in keys)
