# Almighty — CZML template library

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

CZML packet templates for the nine spatial effect families enumerated in [`docs/schema/artifacts.md`](../../docs/schema/artifacts.md) (WS-108). Each file is the wire-format contract for one effect type and is consumed by:

- The capability-gated CZML validator at `services/czml-validator/` (WS-202) — reads `capability_constraints` and cross-references with the issuing entity's capability profile (WS-106 / WS-107).
- The live CZML adapter at `services/czml-adapter/` (WS-503) — reads `base`, substitutes `{{tokens}}` from the artifact + event payload, and publishes the resulting CZML packet to the renderer.

## File format

Every template has three top-level blocks:

| Block | Purpose |
|---|---|
| `base` | CZML packet skeleton with `{{token}}` placeholders. After substitution, this is what the renderer ingests. |
| `params` | Declared parameter set with `type`, `units`, `required`, and (where applicable) `computed_from` notes. The single source of truth for what tokens the kernel must populate. |
| `capability_constraints` | Subset of `params` whose values are gated by the issuing entity's capability profile. Mirrors the `effect_parameter_ranges` keys for this effect family in WS-106 / WS-107 profiles. |

`capability_constraints` deliberately covers only the **tactical** parameters (azimuth, range, radius, dwell, etc.). Identifiers, time-validity, computed positions, and colors are not constrained — they're authored or derived, not chosen.

## Templates

| Template | Effect family | Cesium primitive | Tactical params |
|---|---|---|---|
| [`ew-cone.czml.json`](./ew-cone.czml.json) | EW emission cone | polygon (fan) | `azimuth_deg`, `beamwidth_deg`, `effective_range_m` |
| [`uas-corridor.czml.json`](./uas-corridor.czml.json) | UAS flight corridor | corridor (extruded) | `width_m`, `altitude_band_lower_m`, `altitude_band_upper_m` |
| [`radar-fan.czml.json`](./radar-fan.czml.json) | Radar coverage sector | polygon (fan) | `azimuth_deg`, `sweep_arc_deg`, `range_m` |
| [`jamming-circle.czml.json`](./jamming-circle.czml.json) | Omnidirectional jamming area | ellipse | `radius_m`, `power_w` |
| [`satellite-swath.czml.json`](./satellite-swath.czml.json) | Satellite sensor ground swath | corridor | `swath_width_m`, `pass_duration_s` |
| [`indirect-fire-arc.czml.json`](./indirect-fire-arc.czml.json) | Ballistic indirect-fire trajectory | polyline | `range_m`, `time_of_flight_s`, `dispersion_ellipse_a_m`, `dispersion_ellipse_b_m` |
| [`ir-plume.czml.json`](./ir-plume.czml.json) | IR plume from a hot source | cylinder | `peak_intensity_w_per_sr`, `decay_s` |
| [`masint-cell.czml.json`](./masint-cell.czml.json) | MASINT collection cell | polygon | `polygon_area_m2`, `dwell_s` |
| [`keyhole-footprint.czml.json`](./keyhole-footprint.czml.json) | KH-class imaging footprint | polygon | `polygon_area_m2` |

## Token substitution

Tokens use Mustache-style `{{name}}`. Two replacement modes:

- **Whole-value tokens** — when a JSON string is exactly `"{{token}}"` (no other characters), the kernel replaces the string with the param value at its native type (number, array, etc.). This is how `cartographicDegrees: "{{cone_polygon_positions}}"` becomes a numeric array post-substitution.
- **Interpolated tokens** — when `{{token}}` appears inside a longer string (e.g., the `name` and `description` fields), the param value is stringified and interpolated.

The kernel computes any param marked `"computed_from": [...]` from the listed inputs (e.g., `cone_polygon_positions` is derived from `origin_*`, `azimuth_deg`, `beamwidth_deg`, `effective_range_m`). The smoke-test harness pre-computes these client-side using flat-earth approximations.

## Smoke test

[`_smoke-test.html`](./_smoke-test.html) is a one-page harness that loads each of the nine templates, fills it with sample params, and renders all nine in a 3×3 grid centered on Nashville (36.18°N, 86.78°W) using Cesium 1.123 served from CDN.

```bash
# From repo root, serve the czml/templates directory:
python3 -m http.server 8000 --directory czml/templates
# Then open:
open http://localhost:8000/_smoke-test.html
# Optional: append ?token=<your-cesium-ion-token> for high-res imagery.
```

A status panel in the top-left lists each template with ✓ on render success or ✗ with the error message on failure. WS-201 DoD: all nine show ✓ and all nine appear visibly distinct on the map.

The smoke test does NOT depend on the Resium app shell (WS-501) — it loads vanilla Cesium from CDN so this directory can be validated independently of the renderer PR.

## Validation

JSON syntax is validated as part of the test harness load (any parse error surfaces in the status panel). For full Cesium-CZML schema validation, the `czml-validator` npm package can be used:

```bash
npx czml-validator czml/templates/*.czml.json
```

The capability-side validator (WS-202) is a separate service and validates the *post-substitution* packet, not the template itself.

## Versioning

Each template carries a top-level `version` field. Bump on any change that:

- Adds, removes, or renames a token in `params`.
- Changes the structure of `base` such that downstream renderers need to re-test.
- Tightens `capability_constraints` (loosening is backward-compatible).

WS-202 reads the template by `template_id`; multiple `version`s of the same `template_id` may coexist during a deprecation window.
