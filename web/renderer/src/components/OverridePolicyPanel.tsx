import { useEffect, useState } from "react";
import {
  type OverridePolicy,
  type OverrideScope,
  type OverrideAction,
  createOverridePolicy,
  listOverridePolicies,
  revokeOverridePolicy,
} from "../api/whiteCell";

const SCOPES: OverrideScope[] = ["per-event", "per-agent-per-turn", "per-turn"];
const ACTIONS: OverrideAction[] = ["review", "auto-approve", "auto-block"];

export function OverridePolicyPanel() {
  const [policies, setPolicies] = useState<OverridePolicy[]>([]);
  const [scope, setScope] = useState<OverrideScope>("per-event");
  const [targetId, setTargetId] = useState("");
  const [action, setAction] = useState<OverrideAction>("review");
  const [ttlTurns, setTtlTurns] = useState(0);
  const [rationale, setRationale] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const refresh = () => void listOverridePolicies().then(setPolicies);
  useEffect(() => {
    refresh();
  }, []);

  const valid = targetId.trim().length > 0 && rationale.trim().length > 0;

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid || submitting) return;
    setSubmitting(true);
    try {
      await createOverridePolicy({ scope, target_id: targetId.trim(), action, ttl_turns: ttlTurns, rationale: rationale.trim() });
      setTargetId("");
      setRationale("");
      setTtlTurns(0);
      refresh();
    } finally {
      setSubmitting(false);
    }
  };

  const onRevoke = async (id: string) => {
    await revokeOverridePolicy(id);
    refresh();
  };

  return (
    <section className="white-cell-section">
      <h2>Override policies</h2>

      <form className="override-form" onSubmit={onSubmit}>
        <label className="override-form__row">
          <span>Scope</span>
          <select value={scope} onChange={(e) => setScope(e.target.value as OverrideScope)}>
            {SCOPES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <label className="override-form__row">
          <span>Target ID</span>
          <input
            type="text"
            value={targetId}
            placeholder={scope === "per-event" ? "event_id or pattern" : scope === "per-agent-per-turn" ? "agent_id:turn" : "turn"}
            onChange={(e) => setTargetId(e.target.value)}
          />
        </label>
        <label className="override-form__row">
          <span>Action</span>
          <select value={action} onChange={(e) => setAction(e.target.value as OverrideAction)}>
            {ACTIONS.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </label>
        <label className="override-form__row">
          <span>TTL (turns)</span>
          <input type="number" min={0} value={ttlTurns} onChange={(e) => setTtlTurns(Number(e.target.value))} />
        </label>
        <label className="override-form__row override-form__row--full">
          <span>Rationale</span>
          <textarea
            rows={2}
            value={rationale}
            placeholder="Why this policy?"
            onChange={(e) => setRationale(e.target.value)}
          />
        </label>
        <button
          type="submit"
          className="white-cell-btn white-cell-btn--primary"
          disabled={!valid || submitting}
        >
          {submitting ? "creating…" : "Create policy"}
        </button>
      </form>

      <h3 className="white-cell-subhead">Active policies</h3>
      {policies.length === 0 && <p className="white-cell-hint">No active policies.</p>}
      <table className="policies-table">
        <thead>
          <tr>
            <th>Scope</th>
            <th>Target</th>
            <th>Action</th>
            <th>TTL</th>
            <th>Rationale</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {policies.map((p) => (
            <tr key={p.policy_id}>
              <td><code>{p.scope}</code></td>
              <td><code>{p.target_id}</code></td>
              <td><span className={`pill pill--${p.action}`}>{p.action}</span></td>
              <td>{p.ttl_turns}</td>
              <td>{p.rationale}</td>
              <td>
                <button type="button" className="white-cell-btn white-cell-btn--danger" onClick={() => onRevoke(p.policy_id)}>
                  revoke
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
