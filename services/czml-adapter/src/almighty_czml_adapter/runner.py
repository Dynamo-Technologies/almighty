"""Async WS-subscribe + HTTP-publish runner.

Connects to the WS-304 fan-out service's ``events`` channel, parses
incoming PyRapide event payloads, runs them through the translator,
and publishes the resulting CZML packet (on accept) via HTTP POST to
the fan-out's ``/publish`` ingress on the ``czml_packets`` channel.

Wire protocol per services/websocket/README.md:

  Subscribe (server -> server) over WS:
    ws://host:port/ws?token=<jwt>
    -> { "action": "subscribe", "channel": "events" }

  Inbound message:
    { "type": "message", "channel": "events",
      "tenant_id": "<uuid>", "payload": { ... event JSON ... } }

  Publish (server -> server) over HTTP:
    POST /publish
    Authorization: Bearer <jwt>  (cell_role must be 'white')
    body: { "tenant_id": "...", "channel": "czml_packets", "payload": {...} }

The runner does NOT verify JWTs; it consumes one minted by the caller
(the white-cell-side service identity).

Tests stub the I/O via the protocols at the bottom of this file:
``EventStream`` and ``PacketSink``. Production wires them to
``WsEventStream`` and ``HttpPacketSink``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Protocol
from uuid import UUID

import httpx
import websockets
from almighty_czml_validator import Validator
from almighty_czml_validator.templates import TemplateLoader
from almighty_kernel.dag import KernelEvent

from .models import AdapterResult, ResultKind
from .translator import EntityPositionLookup, translate_event

log = logging.getLogger("almighty.czml_adapter.runner")


# ---------- Protocols (the seams tests use) ---------------------------------


class EventStream(Protocol):
    """Async iterator of incoming KernelEvents for a given tenant."""

    def __aiter__(self) -> AsyncIterator[KernelEvent]: ...


class PacketSink(Protocol):
    """Where accepted CZML packets get sent. Production: HTTP POST to
    the WS-304 /publish endpoint. Tests: an in-memory list."""

    async def publish(self, *, tenant_id: str, packet: dict[str, Any]) -> None: ...
    async def publish_rejected(self, *, tenant_id: str, rejection: dict[str, Any]) -> None: ...


# ---------- WS event stream (production) -------------------------------------


@dataclass
class WsEventStream:
    """Subscribes to the WS-304 ``events`` channel and yields
    KernelEvents. Reconnects with exponential backoff on disconnect."""

    ws_url: str
    jwt: str
    max_reconnect_seconds: float = 30.0

    async def __aiter__(self) -> AsyncIterator[KernelEvent]:
        backoff = 1.0
        while True:
            try:
                async with websockets.connect(
                    f"{self.ws_url}?token={self.jwt}",
                ) as ws:
                    backoff = 1.0
                    await ws.send(json.dumps({"action": "subscribe", "channel": "events"}))
                    async for raw in ws:
                        msg = json.loads(raw)
                        if msg.get("type") != "message":
                            continue
                        if msg.get("channel") != "events":
                            continue
                        try:
                            yield _hydrate_event(msg["payload"])
                        except Exception as exc:  # noqa: BLE001
                            log.warning("dropping malformed event: %s", exc)
            except Exception as exc:  # noqa: BLE001
                log.warning("ws dropped (%s); reconnecting in %.1fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(self.max_reconnect_seconds, backoff * 2.0)


def _hydrate_event(payload: dict[str, Any]) -> KernelEvent:
    """Reconstruct a KernelEvent from a JSON-shaped event payload. The
    write path commits these via the WS-104 NamespacedDag, so the wire
    shape here matches that produced by ``KernelEvent.model_dump()``."""
    return KernelEvent(
        event_id=UUID(payload["event_id"]),
        tenant_id=UUID(payload["tenant_id"]),
        scenario_id=UUID(payload["scenario_id"]),
        turn=int(payload["turn"]),
        source_officer_type=payload["source_officer_type"],
        source_entity_id=UUID(payload["source_entity_id"]),
        action_verb=payload["action_verb"],
        payload=dict(payload.get("payload", {})),
        causal_predecessors=[UUID(p) for p in payload.get("causal_predecessors", [])],
        ts=datetime.fromisoformat(payload["ts"]),
    )


# ---------- HTTP packet sink (production) ------------------------------------


@dataclass
class HttpPacketSink:
    """POSTs accepted CZML packets to the WS-304 /publish endpoint on
    the tenant's ``czml_packets`` channel. Rejected events are POSTed
    on a ``czml_rejected`` virtual channel so AAR can replay them.
    """

    publish_url: str  # e.g. http://websocket:4001/publish
    jwt: str
    timeout_s: float = 10.0
    _client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "HttpPacketSink":
        self._client = httpx.AsyncClient(timeout=self.timeout_s)
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def publish(self, *, tenant_id: str, packet: dict[str, Any]) -> None:
        await self._post("czml_packets", tenant_id, packet)

    async def publish_rejected(self, *, tenant_id: str, rejection: dict[str, Any]) -> None:
        await self._post("czml_rejected", tenant_id, rejection)

    async def _post(self, channel: str, tenant_id: str, payload: dict[str, Any]) -> None:
        if self._client is None:
            raise RuntimeError("HttpPacketSink used outside async context manager")
        body = {"tenant_id": tenant_id, "channel": channel, "payload": payload}
        headers = {"Authorization": f"Bearer {self.jwt}"}
        resp = await self._client.post(self.publish_url, json=body, headers=headers)
        if resp.status_code >= 300:
            log.warning(
                "publish to %s failed: status=%s body=%s",
                channel,
                resp.status_code,
                resp.text,
            )


# ---------- Loop --------------------------------------------------------------


@dataclass
class AdapterRunner:
    """Glue: pulls events from a stream, translates them, and forwards
    accepted packets / rejection notices to the sink."""

    stream: EventStream
    sink: PacketSink
    validator: Validator
    template_loader: TemplateLoader
    capability_profile: dict[str, Any]
    entity_position_lookup: EntityPositionLookup | None = None

    async def run(self) -> None:
        async for event in self.stream:
            result = translate_event(
                event,
                template_loader=self.template_loader,
                validator=self.validator,
                capability_profile=self.capability_profile,
                entity_position_lookup=self.entity_position_lookup,
            )
            await self._dispatch(event, result)

    async def _dispatch(self, event: KernelEvent, result: AdapterResult) -> None:
        tenant = str(event.tenant_id)
        if result.kind is ResultKind.ACCEPTED:
            assert result.packet is not None
            await self.sink.publish(tenant_id=tenant, packet=result.packet)
        elif result.kind is ResultKind.REJECTED:
            await self.sink.publish_rejected(
                tenant_id=tenant,
                rejection={
                    "event_id": str(result.event_id),
                    "family": result.family,
                    "reason": result.reason,
                    "validator_params": result.validator_params,
                    "rejected_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        # SKIPPED: silently ignore (Mover/Commander/Communicator-non-spatial verbs).
