/**
 * Hackathon demo console — single-button EXCON.
 *
 * Reachable at /:tenantId/scenarios/:scenarioId/demo. Opinionated for
 * the 3-minute one-click demo (spec §2):
 *
 *   - Cumberland River map (CesiumScene + the static Nashville vignette CZML).
 *   - Right-side EventLog that drip-feeds events as they land in the DB.
 *   - One big "Advance turn 1" button at the bottom.
 *
 * The button POSTs to /api/tenants/:tid/scenarios/:sid/turns/advance,
 * which on the EC2 control-plane fans out to the spark worker, runs both
 * crews, writes events with causal_predecessors. While the call is in
 * flight + for ~10s after, this view polls /api/events every 750ms so
 * the EventLog populates as Postgres receives writes.
 */

import { useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { JulianDate, type Viewer as CesiumViewer } from "cesium";

import { CesiumScene } from "../components/CesiumScene";
import { CzmlLoader } from "../components/CzmlLoader";
import { CesiumViewerExposer } from "../components/CesiumViewerExposer";
import { EventLog } from "../components/EventLog";
import { DevTokenForm } from "../components/DevTokenForm";
import { useJwtClaims } from "../auth/jwt";
import { getStoredToken } from "../auth/jwt";
import { type DagEvent, fetchEvents } from "../api/aar";

const DEMO_CZML_URL = "/czml/nashville-vignette.czml";

const CONTROL_PLANE_BASE = (() => {
  if (typeof window === "undefined") return "http://localhost:4000";
  // Caddy reverse-proxies /api/* to the control-plane container.
  // Fully-qualified so it works in `new URL(...)` consumers too.
  const override = import.meta.env?.VITE_CONTROL_PLANE_URL;
  if (override) return override;
  return `${window.location.origin}/api`;
})();

export function Demo() {
  const { tenantId, scenarioId } = useParams<{ tenantId: string; scenarioId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  // ?token=... → store + strip from URL so the JWT isn't in the address bar
  // for the duration of the demo. One-shot: if the param's there, persist
  // it to localStorage and remove it so the next reload doesn't re-set.
  useEffect(() => {
    const tokenParam = searchParams.get("token");
    if (tokenParam) {
      try {
        window.localStorage.setItem("almighty.jwt", tokenParam);
      } catch {
        /* localStorage might be blocked; user will see access-denied */
      }
      const next = new URLSearchParams(searchParams);
      next.delete("token");
      setSearchParams(next, { replace: true });
      window.location.reload();
    }
  }, [searchParams, setSearchParams]);

  const claims = useJwtClaims();

  const [, setViewer] = useState<CesiumViewer | null>(null);
  const [events, setEvents] = useState<DagEvent[]>([]);
  const [advancing, setAdvancing] = useState(false);
  const [pollUntil, setPollUntil] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);

  // Park the Cesium clock at a moment inside the static Nashville vignette's
  // availability window where most spatial effects overlap — ~00:05Z is
  // when the radar fan, indirect-fire ellipse, masint cell, satellite
  // swath and UAS corridor are all visible.
  //
  // CzmlDataSource loads ~1s after the viewer mounts and resets the clock
  // to its document packet's currentTime (00:00:00Z, start of interval).
  // Run a short interval that re-parks the clock at 00:05Z for the first
  // ~6s after mount so we win the race regardless of CZML load timing.
  const onViewerReady = useCallback((v: CesiumViewer) => {
    setViewer(v);
    const start = JulianDate.fromIso8601("2026-04-25T00:00:00Z");
    const stop = JulianDate.fromIso8601("2026-04-25T00:10:00Z");
    const sweetSpot = JulianDate.fromIso8601("2026-04-25T00:05:00Z");

    const park = () => {
      v.clock.startTime = start.clone();
      v.clock.stopTime = stop.clone();
      v.clock.currentTime = sweetSpot.clone();
      v.clock.shouldAnimate = false;
      if (v.timeline) v.timeline.zoomTo(v.clock.startTime, v.clock.stopTime);
    };

    park();
    const handle = window.setInterval(park, 250);
    window.setTimeout(() => window.clearInterval(handle), 6000);
  }, []);

  // Poll /events while we're advancing AND for ~10s after the response
  // returns, so late writes drip in.
  useEffect(() => {
    if (!tenantId || !scenarioId || !claims) return;
    const polling = advancing || Date.now() < pollUntil;
    if (!polling) return;

    let cancelled = false;
    const tick = async () => {
      try {
        const evs = await fetchEvents(tenantId, scenarioId);
        if (!cancelled) setEvents(evs);
      } catch {
        /* ignore transient errors during polling */
      }
    };
    void tick();
    const handle = window.setInterval(tick, 750);
    return () => {
      cancelled = true;
      window.clearInterval(handle);
    };
  }, [tenantId, scenarioId, claims, advancing, pollUntil]);

  // One-shot initial load so we render whatever's already in the DB.
  useEffect(() => {
    if (!tenantId || !scenarioId || !claims) return;
    void (async () => {
      try {
        setEvents(await fetchEvents(tenantId, scenarioId));
      } catch {
        /* fine — pre-advance the table can be empty */
      }
    })();
  }, [tenantId, scenarioId, claims]);

  const advance = useCallback(async () => {
    if (!tenantId || !scenarioId) return;
    const token = getStoredToken();
    if (!token) {
      setError("no JWT in localStorage; set one via the dev token form below");
      return;
    }
    setError(null);
    setAdvancing(true);
    try {
      const res = await fetch(
        `${CONTROL_PLANE_BASE}/tenants/${tenantId}/scenarios/${scenarioId}/turns/advance`,
        {
          method: "POST",
          headers: {
            authorization: `Bearer ${token}`,
            "content-type": "application/json",
          },
          // Fastify's strict JSON parser rejects empty body when
          // Content-Type is application/json. The endpoint takes no
          // params, so we send a noop {}.
          body: "{}",
        },
      );
      if (!res.ok) {
        const body = await res.text().catch(() => "(no body)");
        setError(`turn advance failed: ${res.status} ${body.slice(0, 200)}`);
      }
    } catch (e) {
      setError(`turn advance error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setAdvancing(false);
      // Keep polling for 10 more seconds so trailing events land.
      setPollUntil(Date.now() + 10_000);
    }
  }, [tenantId, scenarioId]);

  if (!claims) {
    return (
      <div className="excon-demo excon-demo--locked">
          <div className="excon-demo__locked-card">
          <h1>Almighty — Nashville Cumberland River crossing</h1>
          <p>Set the dev JWT to continue.</p>
          <DevTokenForm />
        </div>
      </div>
    );
  }

  return (
    <div className="excon-demo">
      <header className="excon-demo__header">
        <h1>Almighty — Nashville Cumberland River crossing</h1>
        <p className="excon-demo__subtitle">
          UNCLASSIFIED · DEMONSTRATION ONLY · cloud orchestration · edge inference · auditable causality
        </p>
      </header>
      <div className="excon-demo__body">
        <section className="excon-demo__map">
          <CesiumScene>
            <CesiumViewerExposer onReady={onViewerReady} />
            <CzmlLoader url={DEMO_CZML_URL} />
          </CesiumScene>
        </section>
        <aside className="excon-demo__events">
          <EventLog events={events} overrideDecisions={[]} onSeek={() => {}} />
        </aside>
      </div>
      <footer className="excon-demo__footer">
        <button
          className="excon-demo__advance"
          onClick={advance}
          disabled={advancing}
          type="button"
        >
          {advancing ? "Running on Sparks…" : "Advance turn 1"}
        </button>
        {error && <p className="excon-demo__error">{error}</p>}
      </footer>
    </div>
  );
}
