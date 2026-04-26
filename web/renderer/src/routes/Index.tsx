import { Link } from "react-router-dom";

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
      </ul>
      <p className="index__hint">
        Operator consoles require a JWT with the matching <code>cell_role</code>.
        Append <code>?jwt=&lt;token&gt;</code> to the URL to set one.
      </p>
    </div>
  );
}
