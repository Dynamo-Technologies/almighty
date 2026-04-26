"""Control plane callback client.

Posts crew-completion events to:
    POST {control_plane_url}/tenants/{tenant_id}/scenarios/{scenario_id}/turns/{turn}/crews/{crew}/done

The control plane endpoint that consumes this is owned by the
WS-301/WS-302 follow-up (the turn controller's ``runBetweenTurnAgents``
stub will block until all three crew-done callbacks land). Until that
endpoint exists, the runtime's POST will 404 — the harness logs the
miss and continues so dev iteration isn't blocked. Once the endpoint
ships, behavior tightens.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

LOG = logging.getLogger(__name__)


def post_crew_done(
    *,
    control_plane_url: str,
    tenant_id: str,
    scenario_id: str,
    turn: int,
    crew: str,
    payload: dict[str, Any],
    timeout_s: float = 5.0,
) -> dict[str, Any] | None:
    """POST a crew-done callback. Returns the parsed JSON body on success
    or ``None`` if the endpoint is missing or transport failed."""
    url = (
        f"{control_plane_url.rstrip('/')}"
        f"/tenants/{tenant_id}"
        f"/scenarios/{scenario_id}"
        f"/turns/{turn}"
        f"/crews/{crew}/done"
    )
    body = {
        "tenant_id": tenant_id,
        "scenario_id": scenario_id,
        "turn": turn,
        "crew": crew,
        **payload,
    }
    try:
        resp = httpx.post(url, json=body, timeout=timeout_s)
    except httpx.HTTPError as exc:
        LOG.warning("crew-done callback transport failed url=%s err=%s", url, exc)
        return None

    if resp.status_code == 404:
        # Expected until the control-plane endpoint ships. Soft-fail.
        LOG.info("crew-done endpoint not yet present url=%s (continuing)", url)
        return None
    if resp.status_code >= 400:
        LOG.warning(
            "crew-done callback rejected status=%s url=%s body=%s",
            resp.status_code,
            url,
            resp.text[:500],
        )
        return None

    try:
        return resp.json()
    except ValueError:
        return {}
