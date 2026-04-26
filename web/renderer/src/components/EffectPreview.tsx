import { Entity, EllipseGraphics, PolygonGraphics } from "resium";
import { Cartesian3, Color, PolygonHierarchy } from "cesium";
import type { VerbSpec } from "../verbs/registry";
import type { FormValues } from "./OrderForm";

const PREVIEW_COLOR = Color.fromBytes(255, 220, 100, 140);
const PREVIEW_OUTLINE = Color.fromBytes(255, 220, 100, 220);

type EffectPreviewProps = {
  verb: VerbSpec | null;
  values: FormValues;
};

/**
 * Renders a 50%-opacity ghost shape on the map for the verb the operator is
 * currently drafting. Uses simple Cesium primitives — not the WS-201 templates
 * — because the renderer doesn't have the kernel's geometry-computation step.
 * The shape kind matches what the eventual live packet will render.
 */
export function EffectPreview({ verb, values }: EffectPreviewProps) {
  if (!verb || !verb.spatialArtifact) return null;

  switch (verb.spatialArtifact) {
    case "jamming_circle": {
      const lon = num(values.center_lon_deg);
      const lat = num(values.center_lat_deg);
      const radius = num(values.radius_m);
      if (lon === null || lat === null || !radius) return null;
      return (
        <Entity position={Cartesian3.fromDegrees(lon, lat, 0)}>
          <EllipseGraphics
            semiMajorAxis={radius}
            semiMinorAxis={radius}
            material={PREVIEW_COLOR}
            outline
            outlineColor={PREVIEW_OUTLINE}
          />
        </Entity>
      );
    }
    case "indirect_fire_arc": {
      const lon = num(values.target_lon_deg);
      const lat = num(values.target_lat_deg);
      if (lon === null || lat === null) return null;
      // Shoot a small triangle marker at the impact point — placeholder for
      // a true ballistic arc, which needs a firer position the form doesn't
      // currently capture.
      const halfDeg = 0.001;
      return (
        <Entity>
          <PolygonGraphics
            hierarchy={
              new PolygonHierarchy(
                Cartesian3.fromDegreesArray([
                  lon - halfDeg, lat - halfDeg,
                  lon + halfDeg, lat - halfDeg,
                  lon, lat + halfDeg,
                ]),
              )
            }
            material={PREVIEW_COLOR}
            outline
            outlineColor={PREVIEW_OUTLINE}
          />
        </Entity>
      );
    }
    case "keyhole_footprint": {
      // No map coords on classify; preview is a no-op.
      return null;
    }
    default:
      return null;
  }
}

function num(v: string | number | boolean | null | undefined): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}
