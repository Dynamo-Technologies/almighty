import { Outlet } from "react-router-dom";
import { Banner } from "./components/Banner";

export function App() {
  return (
    <div className="app-shell">
      <Banner position="top" />
      <main className="app-main">
        <Outlet />
      </main>
      <Banner position="bottom" />
    </div>
  );
}
