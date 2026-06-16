/**
 * HistoricoPage tests — T-5.5 run history list and report reopen.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { HistoricoPage } from "../../pages/HistoricoPage";
import * as reportingApi from "../../api/reporting";

vi.mock("../../api/reporting", async (importOriginal) => {
  const actual = await importOriginal<typeof reportingApi>();
  return {
    ...actual,
    listRuns: vi.fn(),
  };
});

const mockRuns = {
  items: [
    {
      id: 42,
      marketplace: "amazon_es",
      status: "completed",
      created_at: "2026-06-10T10:00:00Z",
      completed_at: "2026-06-10T10:05:00Z",
      summary_metrics: { total_skus: 4094, total_errors: 120 },
    },
    {
      id: 7,
      marketplace: "amazon_es",
      status: "failed",
      created_at: "2026-06-09T08:00:00Z",
      completed_at: null,
      summary_metrics: null,
    },
  ],
  total: 2,
  page: 1,
  size: 20,
};

function renderHistorico(initialPath = "/historico") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/historico" element={<HistoricoPage />} />
        <Route path="/historico/:runId/informe" element={<div data-testid="run-report">Informe</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("HistoricoPage", () => {
  it("loads and displays run history entries", async () => {
    vi.mocked(reportingApi.listRuns).mockResolvedValue(mockRuns);

    renderHistorico();

    expect(await screen.findByText(/ejecución #42/i)).toBeInTheDocument();
    expect(screen.getByText(/ejecución #7/i)).toBeInTheDocument();
    expect(screen.getByText(/4094 SKUs/i)).toBeInTheDocument();
  });

  it("navigates to report when clicking a completed run", async () => {
    vi.mocked(reportingApi.listRuns).mockResolvedValue({
      ...mockRuns,
      items: [mockRuns.items[0]],
      total: 1,
    });

    renderHistorico();

    const user = userEvent.setup();
    const link = await screen.findByRole("link", { name: /ver informe.*#42/i });
    expect(link).toHaveAttribute("href", "/historico/42/informe");

    await user.click(link);
    expect(await screen.findByTestId("run-report")).toBeInTheDocument();
  });
});
