import { createBrowserRouter, Navigate } from "react-router-dom";
import { App } from "./App";
import { ScenarioRoot } from "./routes/ScenarioRoot";
import { Index } from "./routes/Index";
import { ExconConsole } from "./routes/ExconConsole";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Index /> },
      {
        path: ":tenantId/scenarios/:scenarioId",
        element: <ScenarioRoot />,
      },
      {
        path: ":tenantId/scenarios/:scenarioId/excon/blue",
        element: <ExconConsole side="blue" />,
      },
      {
        path: ":tenantId/scenarios/:scenarioId/excon/red",
        element: <ExconConsole side="red" />,
      },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
