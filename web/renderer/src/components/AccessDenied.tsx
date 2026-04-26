import { DevTokenForm } from "./DevTokenForm";
import type { CellRole } from "../auth/jwt";

type AccessDeniedProps = {
  required: CellRole;
  actual?: string;
};

export function AccessDenied({ required, actual }: AccessDeniedProps) {
  return (
    <div className="access-denied">
      <h1>ACCESS DENIED</h1>
      <p>This route requires cell role: <strong>{required}</strong></p>
      <p>Your token: {actual ?? "<no token>"}</p>
      <p className="access-denied__hint">
        Set a token with the matching role below — pages re-render once the token is stored.
      </p>
      <DevTokenForm preselect={required} onSet={() => window.location.reload()} />
    </div>
  );
}
