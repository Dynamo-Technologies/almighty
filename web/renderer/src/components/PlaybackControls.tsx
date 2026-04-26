import { useEffect, useState } from "react";
import type { Viewer as CesiumViewer } from "cesium";

type PlaybackControlsProps = {
  viewer: CesiumViewer | null;
};

const SPEEDS: readonly number[] = [0.5, 1, 2, 4, 8, 16];

/**
 * Drives the Cesium clock multiplier + play/pause. The native Cesium
 * Animation widget exposes the same controls but in Cesium's chrome —
 * this component surfaces them in the AAR's own UI so speed selection
 * is one click instead of an analog dial.
 */
export function PlaybackControls({ viewer }: PlaybackControlsProps) {
  const [multiplier, setMultiplier] = useState(1);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!viewer) return;
    setMultiplier(viewer.clock.multiplier);
    setPlaying(viewer.clock.shouldAnimate);
    const onTick = viewer.clock.onTick.addEventListener(() => {
      // Sync local UI state if Cesium's own widget changed it.
      if (viewer.clock.multiplier !== multiplier) setMultiplier(viewer.clock.multiplier);
      if (viewer.clock.shouldAnimate !== playing) setPlaying(viewer.clock.shouldAnimate);
    });
    return () => onTick();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewer]);

  if (!viewer) return null;

  const setSpeed = (n: number) => {
    viewer.clock.multiplier = n;
    setMultiplier(n);
  };
  const togglePlay = () => {
    viewer.clock.shouldAnimate = !viewer.clock.shouldAnimate;
    setPlaying(viewer.clock.shouldAnimate);
  };
  const seekStart = () => {
    viewer.clock.currentTime = viewer.clock.startTime.clone();
  };

  return (
    <div className="playback-controls">
      <button type="button" className="white-cell-btn" onClick={togglePlay}>
        {playing ? "⏸ Pause" : "▶ Play"}
      </button>
      <button type="button" className="white-cell-btn" onClick={seekStart}>
        ⏮ Restart
      </button>
      <span className="playback-controls__speed-label">Speed:</span>
      {SPEEDS.map((s) => (
        <button
          key={s}
          type="button"
          className={`white-cell-btn ${multiplier === s ? "white-cell-btn--primary" : ""}`}
          onClick={() => setSpeed(s)}
        >
          {s}×
        </button>
      ))}
    </div>
  );
}
