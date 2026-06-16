import { createBrowserRouter } from "react-router-dom";

import { AppShell } from "../components/layout/AppShell";
import { DashboardPage } from "../pages/DashboardPage";
import { ConciliacionPage } from "../pages/ConciliacionPage";
import { HistoricoPage } from "../pages/HistoricoPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { RunReportPage } from "../pages/RunReportPage";

/**
 * Application router — T-1.9 skeleton, extended in T-3.9.
 *
 * Top-level route wraps every page in the AppShell (sidebar + main outlet).
 */
export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "conciliacion", element: <ConciliacionPage /> },
      { path: "historico", element: <HistoricoPage /> },
      { path: "historico/:runId/informe", element: <RunReportPage /> },
    ],
  },
  {
    path: "*",
    element: <NotFoundPage />,
  },
]);
