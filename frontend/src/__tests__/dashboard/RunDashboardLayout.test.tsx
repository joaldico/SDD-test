/**
 * RunDashboardLayout — render tests (T-5.1).
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { RunDashboardLayout } from "../../components/dashboard/RunDashboardLayout";
import type { RunMetricsResponse } from "../../types/reporting";

const sampleMetrics: RunMetricsResponse = {
  run_id: 42,
  status: "completed",
  completed_at: "2026-06-16T12:00:00.000Z",
  summary: {
    total_skus: 4094,
    total_errors: 845,
    desynchronized: 66,
  },
  by_sync_status: {
    sent_with_error: 120,
    sent_ok: 3200,
    not_sent: 708,
    desync_feed_only: 62,
    desync_amazon_only: 4,
  },
};

describe("RunDashboardLayout", () => {
  it("renders the dashboard shell with three summary cards", () => {
    render(<RunDashboardLayout runId={42} metrics={sampleMetrics} />);

    expect(screen.getByTestId("run-dashboard")).toBeInTheDocument();
    expect(screen.getByText("Informe de conciliación")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-total-skus")).toHaveTextContent("4,094");
    expect(screen.getByTestId("dashboard-total-errors")).toHaveTextContent("845");
    expect(screen.getByTestId("dashboard-desynchronized")).toHaveTextContent("66");
    expect(screen.getByText("Total SKUs")).toBeInTheDocument();
    expect(screen.getByText("Errores")).toBeInTheDocument();
    expect(screen.getByText("Desincronizados")).toBeInTheDocument();
  });
});
