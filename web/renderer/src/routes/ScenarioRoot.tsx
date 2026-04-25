import { useParams } from "react-router-dom";
import { Excon } from "../layouts/Excon";
import { CesiumScene } from "../components/CesiumScene";

export function ScenarioRoot() {
  const { tenantId, scenarioId } = useParams<{ tenantId: string; scenarioId: string }>();

  return (
    <Excon
      sidebar={
        <div className="placeholder">
          <h2>Sidebar</h2>
          <p>tenant: {tenantId}</p>
          <p>scenario: {scenarioId}</p>
        </div>
      }
      map={<CesiumScene />}
      actions={
        <div className="placeholder">
          <h2>Actions</h2>
          <p>placeholder</p>
        </div>
      }
    />
  );
}
