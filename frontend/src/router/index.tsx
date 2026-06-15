import { createBrowserRouter } from "react-router-dom";

import { AppShell } from "../components/layout/AppShell";
import { DashboardPage } from "../pages/DashboardPage";
import { NotFoundPage } from "../pages/NotFoundPage";

/**
 * Application router — T-1.9 skeleton.
 *
 * Top-level route wraps every page in the AppShell (sidebar + main outlet).
 * Future module routes (M2–M6) are added as children of the root route.
 */
export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <DashboardPage /> },
    ],
  },
  {
    path: "*",
    element: <NotFoundPage />,
  },
]);
