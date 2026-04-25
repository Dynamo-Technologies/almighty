import { useEffect, useRef, useState } from "react";
import { CameraFlyTo, Viewer } from "resium";
import {
  Cartesian3,
  Ion,
  Math as CesiumMath,
  createOsmBuildingsAsync,
  type Viewer as CesiumViewer,
} from "cesium";

const NASHVILLE_LON = -86.78;
const NASHVILLE_LAT = 36.18;
const CAMERA_ALT_M = 8_000;
const FLY_DURATION_S = 1.5;

const ionToken = import.meta.env.VITE_CESIUM_ION_TOKEN;
if (ionToken) {
  Ion.defaultAccessToken = ionToken;
}

const NASHVILLE_DESTINATION = Cartesian3.fromDegrees(
  NASHVILLE_LON,
  NASHVILLE_LAT,
  CAMERA_ALT_M,
);

const NASHVILLE_ORIENTATION = {
  heading: 0,
  pitch: CesiumMath.toRadians(-90),
  roll: 0,
};

export function CesiumScene() {
  const viewerRef = useRef<{ cesiumElement?: CesiumViewer }>(null);
  const [recenterToken, setRecenterToken] = useState(0);

  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement;
    if (!viewer) return;

    let cancelled = false;
    void (async () => {
      try {
        const buildings = await createOsmBuildingsAsync();
        if (cancelled) return;
        viewer.scene.primitives.add(buildings);
      } catch (err) {
        console.warn("OSM Buildings failed to load (ion token missing or invalid?)", err);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <Viewer
        ref={viewerRef}
        full
        timeline={false}
        animation={false}
        baseLayerPicker={false}
        geocoder={false}
        homeButton={false}
        sceneModePicker={false}
        navigationHelpButton={false}
        fullscreenButton={false}
      >
        <CameraFlyTo
          key={recenterToken}
          destination={NASHVILLE_DESTINATION}
          orientation={NASHVILLE_ORIENTATION}
          duration={recenterToken === 0 ? 0 : FLY_DURATION_S}
          once
        />
      </Viewer>
      <button
        type="button"
        className="recenter-btn"
        onClick={() => setRecenterToken((n) => n + 1)}
      >
        Recenter on Nashville
      </button>
    </>
  );
}
