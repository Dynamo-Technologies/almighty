import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useJwtClaims } from "../auth/jwt";
import { AccessDenied } from "../components/AccessDenied";
import { TurnControls } from "../components/TurnControls";
import { OverridePolicyPanel } from "../components/OverridePolicyPanel";
import { ProfileEditor } from "../components/ProfileEditor";
import { ReviewQueue } from "../components/ReviewQueue";
import { fetchTurnState, type TurnSnapshot } from "../api/mock";

export function WhiteCellConsole() {
  const { tenantId, scenarioId } = useParams<{ tenantId: string; scenarioId: string }>();
  const claims = useJwtClaims();
  const [turn, setTurn] = useState<TurnSnapshot | null>(null);

  useEffect(() => {
    void fetchTurnState().then(setTurn);
  }, []);

  if (!claims || claims.cell_role !== "white") {
    return <AccessDenied required="white" actual={claims?.cell_role} />;
  }

  return (
    <div className="white-cell">
      <div className="white-cell__header">
        <h1>White cell — control surface</h1>
        <div className="white-cell__breadcrumb">
          tenant <code>{tenantId}</code> · scenario <code>{scenarioId}</code>
        </div>
      </div>

      <div className="white-cell__sections">
        <TurnControls />
        <OverridePolicyPanel />
        <ProfileEditor turn={turn} />
        <ReviewQueue
          title="Override review queue"
          emptyMessage="No events awaiting review."
        />
        <ReviewQueue
          humanRequiredOnly
          title="Adjudication — human required"
          emptyMessage="No high-stakes events flagged by the adjudicator."
        />
      </div>
    </div>
  );
}
