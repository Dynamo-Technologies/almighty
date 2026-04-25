# Almighty — CZML demo files

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

Hand-authored static CZML files for visual verification of the WS-201 effect templates and for stakeholder demos. These files require **no kernel involvement** — they're pure static CZML, loaded directly into Resium / Cesium.

## Files

| File | Ticket | Purpose |
|---|---|---|
| [`effect-catalog.czml`](./effect-catalog.czml) | WS-203 | Visual regression catalog: 9 effect families laid out in a 3×3 grid centered on Nashville, staggered in time across one hour so each is individually inspectable on the timeline. |
| `nashville-vignette.czml` | WS-204 (planned) | Scripted ~10-minute Cumberland River crossing slice. Not yet authored. |

## Viewing

A standalone vanilla-Cesium viewer is included at [`_view.html`](./_view.html). Serve this directory with any static server and open the viewer in a browser — no Vite, Resium, or build step required.

```bash
# From repo root:
python3 -m http.server 8000 --directory czml/demos
# Then open:
open http://localhost:8000/_view.html
# Pick a different file via query param:
open "http://localhost:8000/_view.html?file=nashville-vignette.czml"
# High-res imagery:
open "http://localhost:8000/_view.html?token=YOUR_VITE_CESIUM_ION_TOKEN_VALUE"
```

The viewer enables Cesium's timeline + animation widgets so you can scrub through staggered activations.

## Layout convention (effect-catalog.czml)

3×3 grid centered on Nashville (36.18°N, 86.78°W) with ~3 km cell spacing:

```
  NW: ew-cone        |  N: uas-corridor    |  NE: radar-fan
  W:  jamming-circle |  C: satellite-swath |  E:  indirect-fire-arc
  SW: ir-plume       |  S: masint-cell     |  SE: keyhole-footprint
```

Each effect uses notional but visible-scale tactical parameters (1–4 km extents). At full-tactical scale (e.g., a 200 km satellite swath), most effects would dominate the entire view; values were tuned to keep the catalog's visual purpose (one effect per cell, identifiable at a glance) intact.

## Time

Catalog availability spans `2026-04-25T00:00:00Z` → `2026-04-25T01:00:00Z`. Effects activate every ~6m 40s in grid order (NW → SE) and remain visible until the end so the scrubber can land on any subset.

## Banner

The unclassified banner is the renderer's responsibility (WS-501 / app-shell). The standalone viewer here renders it on top + bottom of the canvas so the file can be verified in isolation; production use inside the Resium scaffold inherits the banner from `App.tsx`.
