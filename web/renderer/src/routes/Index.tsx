import { Link } from "react-router-dom";

export function Index() {
  return (
    <div className="index">
      <h1>Almighty</h1>
      <p>Pick a scenario to enter:</p>
      <ul>
        <li>
          <Link to="/demo/scenarios/demo">demo / demo</Link>
        </li>
      </ul>
    </div>
  );
}
