import type { JSX } from "react";
import { RouterProvider } from "react-router-dom";

import { router } from "./router";

export function App(): JSX.Element {
  return <RouterProvider router={router} />;
}
