import { createBrowserRouter, Navigate } from "react-router-dom";
import { App } from "./App";
import { ScenarioRoot } from "./routes/ScenarioRoot";
import { Index } from "./routes/Index";

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
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
