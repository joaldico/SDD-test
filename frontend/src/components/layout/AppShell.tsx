import type { JSX } from "react";
import { Outlet } from "react-router-dom";

import { Sidebar } from "./Sidebar";

/**
 * AppShell — top-level layout for the SaaS multi-module shell.
 *
 * Renders a fixed sidebar (navigation) plus a scrollable main content area
 * that hosts child routes via <Outlet />. All future modules are slotted here.
 */
export function AppShell(): JSX.Element {
  return (
    <div style={styles.root}>
      <Sidebar />
      <main style={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}

const styles = {
  root: {
    display: "flex",
    height: "100%",
    overflow: "hidden",
  },
  main: {
    flex: 1,
    overflowY: "auto" as const,
    backgroundColor: "var(--color-bg)",
  },
} as const;
