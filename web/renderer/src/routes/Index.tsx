import { Link } from "react-router-dom";
import { DevTokenForm } from "../components/DevTokenForm";

export function Index() {
  return (
    <div className="index">
      <h1>Almighty</h1>
      <p>Pick a surface:</p>
      <ul>
        <li>
          <Link to="/demo/scenarios/demo">demo / demo (scenario root)</Link>
        </li>
        <li>
          <Link to="/demo/scenarios/demo/excon/blue">demo / demo — EXCON blue</Link>
        </li>
        <li>
          <Link to="/demo/scenarios/demo/excon/red">demo / demo — EXCON red</Link>
        </li>
        <li>
          <Link to="/demo/scenarios/demo/white-cell">demo / demo — white cell control</Link>
        </li>
        <li>
          <Link to="/demo/scenarios/demo/aar">demo / demo — after-action review</Link>
        </li>
      </ul>
      <p className="index__hint">
        Operator consoles require a JWT with the matching <code>cell_role</code>.
        Set one below before navigating.
      </p>
      <DevTokenForm />
    </div>
  );
}
