/**
 * T-1.9 — TDD: AppShell layout component
 *
 * Verifies the main layout shell: sidebar is present, a content area exists,
 * and the router outlet renders child page content.
 * Written before the implementation exists (Red phase).
 */
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, it, expect } from "vitest";

import { AppShell } from "../components/layout/AppShell";

function renderShellWithChild(childContent: string): void {
  const router = createMemoryRouter(
    [
      {
        path: "/",
        element: <AppShell />,
        children: [
          { index: true, element: <div data-testid="child-content">{childContent}</div> }
        ]
      }
    ],
    { initialEntries: ["/"] }
  );
  render(<RouterProvider router={router} />);
}

describe("AppShell", () => {
  it("renders the sidebar inside the shell", () => {
    renderShellWithChild("hello");
    expect(screen.getByRole("navigation", { name: /módulos/i })).toBeInTheDocument();
  });

  it("renders a main content region", () => {
    renderShellWithChild("hello");
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("renders children via router outlet inside main", () => {
    renderShellWithChild("page content here");
    const main = screen.getByRole("main");
    expect(main).toContainElement(screen.getByTestId("child-content"));
  });

  it("displays the application name in the sidebar header", () => {
    renderShellWithChild("hello");
    expect(screen.getByText(/conciliador/i)).toBeInTheDocument();
  });
});
