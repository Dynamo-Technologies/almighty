import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { JulianDate, type Viewer as CesiumViewer } from "cesium";
import { useJwtClaims } from "../auth/jwt";
import { AccessDenied } from "../components/AccessDenied";
import { CesiumScene } from "../components/CesiumScene";
import { CzmlLoader } from "../components/CzmlLoader";
import { CesiumViewerExposer } from "../components/CesiumViewerExposer";
import { PlaybackControls } from "../components/PlaybackControls";
import { EventLog } from "../components/EventLog";
import { ExportBundleButton } from "../components/ExportBundleButton";
import {
  type DagEvent,
  type OverrideDecision,
  fetchEvents,
  fixtureEvents,
  fixtureOverrideDecisions,
} from "../api/aar";

const REPLAY_CZML_URL = "/czml/nashville-vignette.czml";

type LoadState =
  | { kind: "loading" }
  | { kind: "live"; events: DagEvent[]; count: number }
  | { kind: "fixture"; events: DagEvent[]; reason: string }
  | { kind: "error"; reason: string };

export function AarReplay() {
  const { tenantId, scenarioId } = useParams<{ tenantId: string; scenarioId: string }>();
  const claims = useJwtClaims();

  const [viewer, setViewer] = useState<CesiumViewer | null>(null);
  const [load, setLoad] = useState<LoadState>({ kind: "loading" });
  const [overrides] = useState<OverrideDecision[]>(() => fixtureOverrideDecisions());

  const onViewerReady = useCallback((v: CesiumViewer) => setViewer(v), []);

  useEffect(() => {
    if (!claims || !tenantId || !scenarioId) return;
    let cancelled = false;
    void (async () => {
      try {
        const live = await fetchEvents(tenantId, scenarioId);
        if (cancelled) return;
        if (live.length === 0) {
          setLoad({
            kind: "fixture",
            events: fixtureEvents(tenantId, scenarioId),
            reason: "control-plane returned 0 events; replaying Nashville-vignette fixture",
          });
        } else {
          setLoad({ kind: "live", events: live, count: live.length });
        }
      } catch (err) {
        if (cancelled) return;
        setLoad({
          kind: "fixture",
          events: fixtureEvents(tenantId, scenarioId),
          reason: `control-plane unreachable (${err instanceof Error ? err.message : String(err)}); replaying fixture`,
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [claims, tenantId, scenarioId]);

  const seek = useCallback(
    (ts: string) => {
      if (!viewer) return;
      viewer.clock.currentTime = JulianDate.fromIso8601(ts);
    },
    [viewer],
  );

  if (!claims) {
    return <AccessDenied required="white" actual={undefined} />;
  }

  const events = load.kind === "live" || load.kind === "fixture" ? load.events : [];
  const replaySource =
    load.kind === "live" ? "control-plane:/events" : load.kind === "fixture" ? REPLAY_CZML_URL : "—";

  return (
    <div className="aar">
      <header className="aar__header">
        <h1>After-action review</h1>
        <div className="aar__breadcrumb">
          tenant <code>{tenantId}</code> · scenario <code>{scenarioId}</code>
        </div>
        <AarStatus state={load} />
      </header>

      <div className="aar__body">
        <aside className="aar__sidebar">
          <EventLog events={events} overrideDecisions={overrides} onSeek={seek} />
        </aside>

        <section className="aar__map">
          <CesiumScene>
            <CesiumViewerExposer onReady={onViewerReady} />
            <CzmlLoader url={REPLAY_CZML_URL} />
          </CesiumScene>
        </section>

        <aside className="aar__actions">
          <PlaybackControls viewer={viewer} />
          {tenantId && scenarioId && (
            <ExportBundleButton
              tenantId={tenantId}
              scenarioId={scenarioId}
              events={events}
              overrideDecisions={overrides}
              replaySource={replaySource}
            />
          )}
        </aside>
      </div>
    </div>
  );
}

function AarStatus({ state }: { state: LoadState }) {
  if (state.kind === "loading") return <p className="white-cell-hint">loading events…</p>;
  if (state.kind === "error") return <p className="white-cell-hint white-cell-hint--err">{state.reason}</p>;
  if (state.kind === "fixture") return <p className="white-cell-hint white-cell-hint--warn">fixture mode: {state.reason}</p>;
  return <p className="white-cell-hint">live mode: {state.count} events from control-plane</p>;
}
