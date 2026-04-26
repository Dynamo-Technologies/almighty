import { useState, type ReactNode } from "react";
import { CameraFlyTo, Viewer } from "resium";
import { Cartesian3, Ion, Math as CesiumMath } from "cesium";

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

type CesiumSceneProps = {
  children?: ReactNode;
};

export function CesiumScene({ children }: CesiumSceneProps) {
  const [recenterToken, setRecenterToken] = useState(0);

  return (
    <>
      <Viewer
        full
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
        {children}
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
