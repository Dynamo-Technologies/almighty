import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { Excon } from "../layouts/Excon";
import { CesiumScene } from "../components/CesiumScene";
import { CzmlLoader } from "../components/CzmlLoader";
import { CzmlSelector, DEMO_URLS, type DemoKey } from "../components/CzmlSelector";

export function ScenarioRoot() {
  const { tenantId, scenarioId } = useParams<{ tenantId: string; scenarioId: string }>();
  const [searchParams] = useSearchParams();
  const isDev = searchParams.get("dev") === "1";

  // In dev mode, default to the catalog so the toggle UX is immediately visible.
  // Outside dev mode, no static CZML is loaded — production live data lands in WS-503.
  const [demo, setDemo] = useState<DemoKey | null>(isDev ? "catalog" : null);

  return (
    <Excon
      sidebar={
        <div className="placeholder">
          <h2>Sidebar</h2>
          <p>tenant: {tenantId}</p>
          <p>scenario: {scenarioId}</p>
        </div>
      }
      map={
        <>
          <CesiumScene>
            {demo && <CzmlLoader key={demo} url={DEMO_URLS[demo]} />}
          </CesiumScene>
          {isDev && <CzmlSelector value={demo} onChange={setDemo} />}
        </>
      }
      actions={
        <div className="placeholder">
          <h2>Actions</h2>
          <p>placeholder</p>
        </div>
      }
    />
  );
}
