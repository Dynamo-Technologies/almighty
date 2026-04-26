import { useEffect } from "react";
import { useCesium } from "resium";
import type { Viewer as CesiumViewer } from "cesium";

type CesiumViewerExposerProps = {
  onReady: (viewer: CesiumViewer) => void;
};

/**
 * Helper child of <Viewer> that hands the underlying Cesium viewer back to
 * a parent via callback. Used by AAR-side controls that need to drive the
 * clock (multiplier, currentTime, shouldAnimate) imperatively.
 */
export function CesiumViewerExposer({ onReady }: CesiumViewerExposerProps) {
  const { viewer } = useCesium();
  useEffect(() => {
    if (viewer) onReady(viewer);
  }, [viewer, onReady]);
  return null;
}
