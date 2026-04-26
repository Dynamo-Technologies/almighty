import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Excon } from "../layouts/Excon";
import { CesiumScene } from "../components/CesiumScene";
import { EntitySidebar } from "../components/EntitySidebar";
import { OrderForm, type FormValues } from "../components/OrderForm";
import { EffectPreview } from "../components/EffectPreview";
import { TurnState } from "../components/TurnState";
import { AccessDenied } from "../components/AccessDenied";
import { useJwtClaims, type CellRole } from "../auth/jwt";
import {
  type EntityForce,
  type EntitySummary,
  type TurnSnapshot,
  fetchFriendlyEntities,
  fetchTurnState,
  submitOrder,
} from "../api/mock";
import type { VerbSpec } from "../verbs/registry";

type ExconConsoleProps = {
  side: "blue" | "red";
};

const FORCE_FOR_SIDE: Record<"blue" | "red", EntityForce> = {
  blue: "BLUE",
  red: "RED",
};

export function ExconConsole({ side }: ExconConsoleProps) {
  const { tenantId, scenarioId } = useParams<{ tenantId: string; scenarioId: string }>();
  const claims = useJwtClaims();
  const requiredRole: CellRole = side;

  const [entities, setEntities] = useState<EntitySummary[]>([]);
  const [entitiesLoading, setEntitiesLoading] = useState(true);
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);

  const [turn, setTurn] = useState<TurnSnapshot | null>(null);

  const [draftVerb, setDraftVerb] = useState<VerbSpec | null>(null);
  const [draftValues, setDraftValues] = useState<FormValues>({});
  const [submitting, setSubmitting] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  // Load fixtures on mount. Re-fetch when the scenario changes.
  useEffect(() => {
    let cancelled = false;
    setEntitiesLoading(true);
    void (async () => {
      const [e, t] = await Promise.all([
        fetchFriendlyEntities(FORCE_FOR_SIDE[side]),
        fetchTurnState(),
      ]);
      if (cancelled) return;
      setEntities(e);
      setTurn(t);
      setEntitiesLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [side, scenarioId]);

  const handleDraft = useCallback((verb: VerbSpec | null, values: FormValues) => {
    setDraftVerb(verb);
    setDraftValues(values);
  }, []);

  const handleSubmit = useCallback(
    async (verb: VerbSpec, values: FormValues) => {
      if (!claims || !tenantId || !scenarioId) return;
      setSubmitting(true);
      try {
        const res = await submitOrder({
          tenant_id: tenantId,
          scenario_id: scenarioId,
          cell_role: claims.cell_role,
          officer: verb.officer,
          verb: verb.verb,
          payload: values,
        });
        setLastResult(
          res.accepted ? `accepted ${verb.verb} → ${res.event_id}` : `rejected: ${res.reason ?? "unknown"}`,
        );
      } catch (err) {
        setLastResult(`error: ${err instanceof Error ? err.message : String(err)}`);
      } finally {
        setSubmitting(false);
      }
    },
    [claims, tenantId, scenarioId],
  );

  if (!claims || claims.cell_role !== requiredRole) {
    return <AccessDenied required={requiredRole} actual={claims?.cell_role} />;
  }

  const locked = turn?.turn_state === "advancing";

  return (
    <Excon
      sidebar={
        <EntitySidebar
          entities={entities}
          selectedId={selectedEntityId}
          onSelect={setSelectedEntityId}
          loading={entitiesLoading}
        />
      }
      map={
        <>
          <CesiumScene>
            <EffectPreview verb={draftVerb} values={draftValues} />
          </CesiumScene>
          <div className="excon-overlay">
            <TurnState snapshot={turn} />
            <div className={`side-badge side-badge--${side}`}>{side.toUpperCase()} CELL</div>
          </div>
        </>
      }
      actions={
        <div className="actions-pane">
          <OrderForm
            locked={locked}
            onDraft={handleDraft}
            onSubmit={handleSubmit}
            submitting={submitting}
          />
          {lastResult && <p className="actions-pane__result">{lastResult}</p>}
        </div>
      }
    />
  );
}
