import { useEffect, useState, useCallback } from "react";
import {
  type PendingReviewItem,
  type ReviewDecision,
  decideReview,
  listPendingReview,
} from "../api/whiteCell";

type ReviewQueueProps = {
  /** When true, render only items flagged human_required=true (the WS-405 surface). */
  humanRequiredOnly?: boolean;
  title: string;
  emptyMessage: string;
};

export function ReviewQueue({ humanRequiredOnly = false, title, emptyMessage }: ReviewQueueProps) {
  const [items, setItems] = useState<PendingReviewItem[]>([]);
  const [decidingId, setDecidingId] = useState<string | null>(null);

  const refresh = useCallback(() => {
    void listPendingReview().then((all) => {
      setItems(humanRequiredOnly ? all.filter((i) => i.human_required) : all.filter((i) => !i.human_required));
    });
  }, [humanRequiredOnly]);

  useEffect(refresh, [refresh]);

  const decide = async (item: PendingReviewItem, decision: ReviewDecision) => {
    setDecidingId(item.event_id);
    try {
      await decideReview(item.event_id, decision);
      refresh();
    } finally {
      setDecidingId(null);
    }
  };

  return (
    <section className={`white-cell-section ${humanRequiredOnly ? "white-cell-section--adjudication" : ""}`}>
      <h2>{title}</h2>
      {items.length === 0 && <p className="white-cell-hint">{emptyMessage}</p>}
      {items.map((item) => (
        <div key={item.event_id} className="review-item">
          <div className="review-item__header">
            <span className="review-item__verb"><code>{item.proposed_verb}</code></span>
            <span className="review-item__agent">{item.agent_id}</span>
            <span className="review-item__time">{item.arrived_at}</span>
          </div>
          <div className="review-item__entity">
            from <strong>{item.source_entity_name}</strong>
            <span className="review-item__id"> ({item.source_entity_id.slice(0, 8)}…)</span>
          </div>
          <div className="review-item__profile">
            profile: <code>{item.capability_profile_ref}</code> · validator: <code>{item.validator_result}</code>
          </div>
          <pre className="review-item__payload">{JSON.stringify(item.proposed_payload, null, 2)}</pre>
          <div className="review-item__buttons">
            <button
              type="button"
              className="white-cell-btn white-cell-btn--primary"
              disabled={decidingId === item.event_id}
              onClick={() => decide(item, "approve")}
            >
              Approve
            </button>
            <button
              type="button"
              className="white-cell-btn white-cell-btn--danger"
              disabled={decidingId === item.event_id}
              onClick={() => decide(item, "block")}
            >
              Block
            </button>
            <button
              type="button"
              className="white-cell-btn"
              disabled={decidingId === item.event_id}
              onClick={() => decide(item, "edit-and-approve")}
            >
              Edit + approve
            </button>
            <button
              type="button"
              className="white-cell-btn"
              disabled={decidingId === item.event_id}
              onClick={() => decide(item, "inject-manual")}
            >
              Inject manual
            </button>
          </div>
        </div>
      ))}
    </section>
  );
}
