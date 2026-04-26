import { useState } from "react";
import {
  type CellRole,
  clearStoredToken,
  getStoredToken,
  mintDevJwt,
  setStoredToken,
} from "../auth/jwt";

const ROLES: readonly CellRole[] = ["white", "blue", "red", "observer"];
const DEFAULT_TENANT = "11111111-1111-4111-8111-111111111111";

type DevTokenFormProps = {
  /** Which role this surface is asking for. Pre-selects the dropdown. */
  preselect?: CellRole;
  /** Where to land after a token is set. Defaults to current location. */
  onSet?: () => void;
};

export function DevTokenForm({ preselect, onSet }: DevTokenFormProps) {
  const [role, setRole] = useState<CellRole>(preselect ?? "white");
  const [tenantId, setTenantId] = useState<string>(DEFAULT_TENANT);
  const [storedPreview, setStoredPreview] = useState<string | null>(getStoredToken());

  const apply = () => {
    const token = mintDevJwt({ tenant_id: tenantId, cell_role: role });
    setStoredToken(token);
    setStoredPreview(token);
    onSet?.();
  };

  const clear = () => {
    clearStoredToken();
    setStoredPreview(null);
  };

  return (
    <div className="dev-token-form">
      <h2>Dev token</h2>
      <p className="dev-token-form__hint">
        Mints an unsigned <code>alg:none</code> JWT and stores it in <code>localStorage</code>.
        The server rejects these — they're only used by the renderer for client-side route gating.
      </p>

      <label className="dev-token-form__row">
        <span>Cell role</span>
        <select value={role} onChange={(e) => setRole(e.target.value as CellRole)}>
          {ROLES.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
      </label>

      <label className="dev-token-form__row">
        <span>Tenant ID</span>
        <input type="text" value={tenantId} onChange={(e) => setTenantId(e.target.value)} />
      </label>

      <div className="dev-token-form__buttons">
        <button type="button" className="white-cell-btn white-cell-btn--primary" onClick={apply}>
          Set token
        </button>
        <button type="button" className="white-cell-btn" onClick={clear} disabled={!storedPreview}>
          Clear token
        </button>
      </div>

      {storedPreview && (
        <p className="dev-token-form__preview">
          stored: <code>{storedPreview.slice(0, 40)}…</code>
        </p>
      )}
    </div>
  );
}
