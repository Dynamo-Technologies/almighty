# `almighty-czml-adapter` — WS-503 (kernel side)

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

Live PyRapide → CZML adapter. Subscribes to a tenant's `events` channel
on the WS-304 fan-out service, translates each spatial-artifact-bearing
event into a post-substitution CZML packet (gated by the WS-202
validator), and publishes the packet to the tenant's `czml_packets`
channel.

**Joint ownership** with WS-503 renderer side (Alex). This package is
the kernel-side adapter; the renderer-side React + Resium component
that consumes `czml_packets` is owned by Alex. See
[§ Renderer-side integration contract](#renderer-side-integration-contract-for-alex)
below for the wire shape.

## Pipeline

```
            ┌─────────────────┐
            │  WS-304 events  │   (tenant-scoped fan-out subscription)
            │     channel     │
            └─────────┬───────┘
                      │
                      ▼
        ┌──────────────────────────────┐
        │   AdapterRunner.run()        │
        │                              │
        │   for event in stream:       │
        │     result = translate_event │
        │     if ACCEPTED -> publish   │ ─────► HTTP POST /publish
        │     if REJECTED -> publish   │       channel=czml_packets
        │       on czml_rejected       │       payload={CZML packet}
        │     if SKIPPED  -> ignore    │
        └──────────────────────────────┘
```

The translator is pure (no I/O); the runner glues it to the WS-304
service. Tests run the translator in-process and the runner against
stub stream / sink — no live WS or HTTP needed.

## Family coverage (v1: 7 of 9)

| Family | Trigger | Validator gate |
|---|---|---|
| `jamming_circle` | `Communicator.jam` OR `Effector.disable(method=EW)` | `radius_m`, `power_w` |
| `indirect_fire_arc` | `Effector.engage`/`suppress`/`destroy` OR `Effector.disable(method=KINETIC)` | `range_m`, `time_of_flight_s`, `dispersion_ellipse_a_m`, `dispersion_ellipse_b_m` |
| `radar_fan` | `Sensor.detect`/`track` with `modality=RADAR` | `azimuth_deg`, `sweep_arc_deg`, `range_m` |
| `ew_cone` | `Sensor.detect` with `modality=RF` | `azimuth_deg`, `beamwidth_deg`, `effective_range_m` |
| `masint_cell` | `Sensor.detect`/`classify` with `modality ∈ {ACOUSTIC, SEISMIC, MASINT_MULTI}` | `polygon_area_m2`, `dwell_s` |
| `keyhole_footprint` | `Sensor.classify` (non-MASINT modality) | `polygon_area_m2` |
| `uas_corridor` | `Communicator.relay` with `payload.is_airborne=True` | `altitude_band_lower_m`, `altitude_band_upper_m`, `width_m` |

Per the runbook + WS-108 § 6 verb-emission table.

**Deferred to v2:**

- **`ir_plume`** — needs kernel-side follow-on event emission from `Effector.destroy`. The kernel doesn't emit follow-on events yet, so v1's destroy events produce only `indirect_fire_arc`.
- **`satellite_swath`** — needs SPACE_UNIT entity-type signal that the adapter doesn't currently get from the events stream. Requires either an `entity_type` field on the event payload or an entity-table lookup.

## Result semantics

Every event yields one `AdapterResult`:

```python
@dataclass
class AdapterResult:
    kind: ResultKind   # ACCEPTED | REJECTED | SKIPPED
    event_id: UUID
    family: str | None
    packet: dict[str, Any] | None     # set on ACCEPTED
    reason: str | None                # set on REJECTED / SKIPPED
    validator_params: dict[str, Any]  # set on ACCEPTED / REJECTED
```

- **ACCEPTED** — `packet` ready to publish on `czml_packets`.
- **REJECTED** — validator rejected; runner emits a `czml_rejected` audit on a virtual channel of the same name (so AAR can replay rejections per WS-108 § 7.4).
- **SKIPPED** — non-spatial verb (Mover / Commander / Communicator non-spatial) OR `EO_IR` detect (no template in v1). No packet, no audit.

## Renderer-side integration contract (for Alex)

The renderer-side component (replacing WS-502's static-only loader)
consumes `czml_packets` over the WS-304 channel.

### Subscribe

Per [services/websocket/README.md](../websocket/README.md):

```js
const ws = new WebSocket(`wss://host:port/ws?token=${jwt}`);
ws.onopen = () => ws.send(JSON.stringify({
  action: "subscribe",
  channel: "czml_packets",
}));
ws.onmessage = (msg) => {
  const env = JSON.parse(msg.data);
  if (env.type !== "message" || env.channel !== "czml_packets") return;
  // env.tenant_id, env.payload (a CZML packet)
  applyPacket(env.payload);
};
```

### Packet shape

Each `payload` is a single Cesium CZML packet — exactly the post-substituted
`base` block from the corresponding WS-201 template. For example, a
`jamming_circle`:

```json
{
  "id": "<artifact-uuid>",
  "name": "Jamming circle — <owning-entity-uuid>",
  "description": "Jamming circle, radius 2000.0 m, power 500.0 W, band L",
  "availability": "2026-04-25T18:00:00+00:00/2026-04-25T18:01:30+00:00",
  "position": { "cartographicDegrees": [-86.79, 36.175, 170.0] },
  "ellipse": {
    "semiMajorAxis": 2000.0,
    "semiMinorAxis": 2000.0,
    "material": { "solidColor": { "color": { "rgba": [255, 80, 60, 90] } } },
    "outline": true,
    "outlineColor": { "rgba": [255, 80, 60, 220] },
    "heightReference": "CLAMP_TO_GROUND"
  }
}
```

The adapter substitutes every `{{token}}` placeholder. Renderer can
hand the packet straight to a Resium `<CzmlDataSource>` incremental
load (no further parsing). One packet ≈ one feature on the map; the
`id` is the artifact UUID and is stable across re-publishes.

### Live/static toggle

Replace WS-502's static-only loader with a toggle:

- **Static mode** — load a `.czml` file directly (current WS-502 behavior).
- **Live mode** — open the WS-304 subscription above, accumulate packets into a `<CzmlDataSource>` instance, and let Resium re-render incrementally as packets arrive.

### Deletion (v2)

Per the runbook, the adapter should publish CZML packets with `delete: true` when an effect ends. v1 does NOT do this — the templates carry `availability` time windows and the renderer can rely on Cesium's own time-based hide / show. v2 will add explicit deletion publishing when the kernel grows artifact-end events.

### Capability gating signal (renderer doesn't need to do anything)

The DoD requires "rejected packets do not render." That holds because rejected events never get published — the validator gates on the adapter side. The renderer doesn't see them. AAR replay (WS-506) reads the `czml_rejected` audit channel separately for post-mortem rendering of what was blocked.

## Stack

- Python ≥ 3.11
- `fastapi` for the `/healthz` shell
- `httpx` (async) for `POST /publish`
- `websockets` for the `events` subscription
- `pydantic` 2.6+
- Editable deps on `almighty-kernel` (KernelEvent shape) and `almighty-czml-validator` (in-process validator + template loader)

## Run

```bash
# From this directory:
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ../../kernel
pip install -e ../czml-validator
pip install -e ".[test]"

# Run the test suite
pytest -v

# Run the FastAPI shell (healthz only — no auto-start of the runner)
uvicorn almighty_czml_adapter.app:app --reload --port 8012
```

To start the runner against a real WS-304 service, wire it manually:

```python
import asyncio
from almighty_czml_validator import Validator
from almighty_czml_validator.templates import TemplateLoader
from almighty_czml_adapter.runner import AdapterRunner, HttpPacketSink, WsEventStream

async def main():
    template_loader = TemplateLoader()
    validator = Validator(template_loader=template_loader)
    stream = WsEventStream(ws_url="ws://websocket:4001/ws", jwt=os.environ["ADAPTER_JWT"])
    async with HttpPacketSink(
        publish_url="http://websocket:4001/publish",
        jwt=os.environ["ADAPTER_JWT"],
    ) as sink:
        runner = AdapterRunner(
            stream=stream,
            sink=sink,
            validator=validator,
            template_loader=template_loader,
            capability_profile=load_profile_for_tenant(),  # caller wires this
        )
        await runner.run()

asyncio.run(main())
```

The adapter JWT must carry `cell_role: 'white'` because WS-304's `/publish` endpoint requires it.

## Tests — 24 passing

```
$ pytest -v
tests/test_app.py .                                                      [  4%]
tests/test_runner.py ..                                                  [ 12%]
tests/test_translator.py .....................                           [100%]
24 passed in 0.08s
```

- **7 family happy-paths** — one per v1 family, asserting `kind == ACCEPTED` and the substituted packet shape (whole-value tokens become native types; interpolated tokens fill into description / name strings).
- **3 reject paths** — jam over peer's power_w cap; us-bct lacks `jam` (validator's verb gate fires); engage over us-bct's range_m cap. Confirms capability-gating is exercised end-to-end.
- **9 skip paths** — 8 non-spatial verbs (Mover, Commander, Communicator non-spatial) + `EO_IR` detect.
- **2 token-substitution sanity** — packet.id is the synthesized artifact UUID (not literal `{{artifact_id}}`); validator_params reflected on result for AAR audit.
- **2 runner integration tests** — `_StreamFromList` + `_CollectingSink` stubs; verifies accepted → publish path, rejected → publish_rejected path, skipped → silently dropped, empty stream is a no-op.
- **1 HTTP smoke** — `/healthz` returns `{status: ok}`.

Real `KernelEvent`, real `Validator`, real `TemplateLoader`, real WS-107 profiles loaded from disk. No mocks of upstream contracts.

## Layout

```
services/czml-adapter/
├── pyproject.toml
├── README.md                                       ← this file
├── src/almighty_czml_adapter/
│   ├── __init__.py                                 ← exports translate_event, AdapterResult, EntityPosition
│   ├── models.py                                   ← AdapterResult tagged union, ResultKind, EntityPosition
│   ├── families.py                                 ← per-family detector + token builder + validator-param keys
│   ├── translator.py                               ← translate_event (pure, no I/O)
│   ├── runner.py                                   ← AdapterRunner + WsEventStream + HttpPacketSink
│   └── app.py                                      ← FastAPI: /healthz only
└── tests/
    ├── conftest.py                                 ← real upstream fixtures
    ├── test_translator.py                          ← family happy + reject + skip
    ├── test_runner.py                              ← runner glue with stub stream/sink
    └── test_app.py                                 ← /healthz
```

## Notes / open questions

- **Entity-position lookup is caller-supplied.** v1's default callback returns a Nashville-anchored point so demos render somewhere visible. Production callers MUST supply a real lookup that reads from the entities table — that's a v2 integration when this adapter is wired into the running stack.
- **Capability-profile-per-tenant** is a single dict in v1. A real deployment will want a `lookup_profile_for(tenant_id, agent_entity_id)` callback. Same v2 wiring as the entity lookup.
- **No `ir_plume` or `satellite_swath`.** Documented above — both need upstream changes (follow-on event emission and entity-type signal respectively).
- **No deletion publishing yet.** Templates' `availability` windows handle most cases; explicit `delete: true` publishing is a v2 candidate.
- **Adapter does NOT post to WS-303.** Rejection audit is sent on the `czml_rejected` virtual channel. WS-506 (AAR) consumes it. v2 may also wire to WS-303's `override_decisions` table for full audit-trail consolidation.

## See also

- [`docs/schema/officer-interfaces.md`](../../docs/schema/officer-interfaces.md) — verb signatures (WS-105).
- [`docs/schema/artifacts.md`](../../docs/schema/artifacts.md) — verb→artifact mapping (WS-108).
- [`czml/templates/README.md`](../../czml/templates/README.md) — template format + token substitution rules (WS-201).
- [`services/czml-validator/`](../czml-validator/) — in-process validator (WS-202).
- [`services/websocket/`](../websocket/) — fan-out service this adapter subscribes / publishes to (WS-304).
- WS-503 renderer side (Alex) — the React + Resium component that consumes `czml_packets`.
- WS-506 (#31) — AAR replay; consumes `czml_rejected` audit channel.
