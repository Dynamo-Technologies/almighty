import { buildAarEnvelope, downloadAarBundle, type DagEvent, type OverrideDecision } from "../api/aar";

type ExportBundleButtonProps = {
  tenantId: string;
  scenarioId: string;
  events: DagEvent[];
  overrideDecisions: OverrideDecision[];
  replaySource: string;
};

export function ExportBundleButton(props: ExportBundleButtonProps) {
  const onClick = () => {
    const envelope = buildAarEnvelope({
      tenantId: props.tenantId,
      scenarioId: props.scenarioId,
      events: props.events,
      overrideDecisions: props.overrideDecisions,
      replaySource: props.replaySource,
    });
    downloadAarBundle(envelope);
  };
  return (
    <button type="button" className="white-cell-btn white-cell-btn--primary" onClick={onClick}>
      Export AAR bundle
    </button>
  );
}
