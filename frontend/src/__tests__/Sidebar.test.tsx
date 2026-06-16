/**
 * T-1.9 — TDD: Sidebar component
 *
 * Verifies that the sidebar navigation renders all top-level module entries
 * that the shell must expose, including those marked as coming-soon.
 * Tests intentionally reference the DOM roles/labels required by the spec
 * BEFORE the implementation exists (Red phase).
 */
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";

import { Sidebar } from "../components/layout/Sidebar";

function renderSidebar(): void {
  render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>
  );
}

describe("Sidebar", () => {
  it("renders a navigation landmark", () => {
    renderSidebar();
    expect(screen.getByRole("navigation", { name: /módulos/i })).toBeInTheDocument();
  });

  it("renders the Dashboard link", () => {
    renderSidebar();
    const link = screen.getByRole("link", { name: /dashboard/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/");
  });

  it("renders the Conciliación entry", () => {
    renderSidebar();
    expect(screen.getByText(/conciliación/i)).toBeInTheDocument();
  });

  it("renders the Histórico entry", () => {
    renderSidebar();
    expect(screen.getByText(/histórico/i)).toBeInTheDocument();
  });

  it("renders the Taxonomía entry", () => {
    renderSidebar();
    expect(screen.getByText(/taxonomía/i)).toBeInTheDocument();
  });

  it("renders Taxonomía as an active link", () => {
    renderSidebar();
    const link = screen.getByRole("link", { name: /taxonomía/i });
    expect(link).toHaveAttribute("href", "/taxonomia");
  });

  it("renders Histórico as an active link", () => {
    renderSidebar();
    const link = screen.getByRole("link", { name: /histórico/i });
    expect(link).toHaveAttribute("href", "/historico");
  });
});
