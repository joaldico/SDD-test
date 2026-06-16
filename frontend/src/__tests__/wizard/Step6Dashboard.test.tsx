/**
 * Step6Dashboard — integration render tests (T-5.1).
 */

import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Step6Dashboard } from "../../components/wizard/steps/Step6Dashboard";
import type { RunMetricsResponse } from "../../types/reporting";

const sampleMetrics: RunMetricsResponse = {
  run_id: 7,
  status: "completed",
  completed_at: "2026-06-16T12:00:00.000Z",
  summary: {
    total_skus: 120,
    total_errors: 15,
    desynchronized: 7,
  },
  by_sync_status: {
    sent_with_error: 3,
    sent_ok: 100,
    not_sent: 17,
    desync_feed_only: 5,
    desync_amazon_only: 2,
  },
};

describe("Step6Dashboard", () => {
  it("shows loading state while metrics are fetched", () => {
    const onFetchMetrics = vi.fn(
      () => new Promise<RunMetricsResponse>(() => {
        /* never resolves */
      })
    );

    render(
      <Step6Dashboard runId={7} onFetchMetrics={onFetchMetrics} />
    );

    expect(screen.getByTestId("dashboard-loading")).toBeInTheDocument();
    expect(onFetchMetrics).toHaveBeenCalledOnce();
  });

  it("renders dashboard summary cards when metrics load", async () => {
    const onFetchMetrics = vi.fn().mockResolvedValue(sampleMetrics);

    render(
      <Step6Dashboard runId={7} onFetchMetrics={onFetchMetrics} />
    );

    await waitFor(() => {
      expect(screen.getByTestId("step6-dashboard")).toBeInTheDocument();
    });

    expect(screen.getByTestId("dashboard-total-skus")).toHaveTextContent("120");
    expect(screen.getByTestId("dashboard-total-errors")).toHaveTextContent("15");
    expect(screen.getByTestId("dashboard-desynchronized")).toHaveTextContent("7");
  });

  it("shows error state when metrics fetch fails", async () => {
    const onFetchMetrics = vi.fn().mockRejectedValue(new Error("Metrics not ready"));

    render(
      <Step6Dashboard runId={7} onFetchMetrics={onFetchMetrics} />
    );

    await waitFor(() => {
      expect(screen.getByTestId("dashboard-error")).toBeInTheDocument();
    });

    expect(screen.getByText("Metrics not ready")).toBeInTheDocument();
  });
});
