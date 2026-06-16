/**
 * Step6Dashboard — integration render tests (T-5.1 / T-5.4).
 */

import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Step6Dashboard } from "../../components/wizard/steps/Step6Dashboard";
import type {
  CatalogHealthResponse,
  FamiliesReportResponse,
  RunMetricsResponse,
} from "../../types/reporting";

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

const sampleFamilies: FamiliesReportResponse = {
  run_id: 7,
  sin_clasificar_warning: false,
  families: [],
};

const sampleCatalog: CatalogHealthResponse = {
  run_id: 7,
  total: 0,
  page: 1,
  page_size: 50,
  items: [],
};

const noopSkus = vi.fn().mockResolvedValue({
  run_id: 7,
  family_code: null,
  error_code: null,
  items: [],
  total: 0,
  page: 1,
  page_size: 50,
});
const noopExport = vi.fn().mockResolvedValue(undefined);

describe("Step6Dashboard", () => {
  it("shows loading state while report data is fetched", () => {
    const pending = () => new Promise<never>(() => {
      /* never resolves */
    });

    render(
      <Step6Dashboard
        runId={7}
        onFetchMetrics={vi.fn(pending)}
        onFetchFamilies={vi.fn(pending)}
        onFetchCatalog={vi.fn(pending)}
        onFetchSkusForCode={noopSkus}
        onExport={noopExport}
      />,
    );

    expect(screen.getByTestId("dashboard-loading")).toBeInTheDocument();
  });

  it("renders dashboard summary cards and tabbed views when data loads", async () => {
    const onFetchMetrics = vi.fn().mockResolvedValue(sampleMetrics);
    const onFetchFamilies = vi.fn().mockResolvedValue(sampleFamilies);
    const onFetchCatalog = vi.fn().mockResolvedValue(sampleCatalog);

    render(
      <Step6Dashboard
        runId={7}
        onFetchMetrics={onFetchMetrics}
        onFetchFamilies={onFetchFamilies}
        onFetchCatalog={onFetchCatalog}
        onFetchSkusForCode={noopSkus}
        onExport={noopExport}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("step6-dashboard")).toBeInTheDocument();
    });

    expect(onFetchMetrics).toHaveBeenCalledOnce();
    expect(onFetchFamilies).toHaveBeenCalledOnce();
    await waitFor(() => {
      expect(onFetchCatalog).toHaveBeenCalledWith({ page: 1, page_size: 50 });
    });
    expect(screen.getByTestId("dashboard-total-skus")).toHaveTextContent("120");
    expect(screen.getByTestId("dashboard-tab-catalog")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-tab-families")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-tab-metrics")).toBeInTheDocument();
    expect(screen.getByTestId("export-xlsx-button")).toBeInTheDocument();
    expect(screen.getByTestId("export-csv-button")).toBeInTheDocument();
  });

  it("shows error state when any fetch fails", async () => {
    const onFetchMetrics = vi.fn().mockRejectedValue(new Error("Report not ready"));

    render(
      <Step6Dashboard
        runId={7}
        onFetchMetrics={onFetchMetrics}
        onFetchFamilies={vi.fn().mockResolvedValue(sampleFamilies)}
        onFetchCatalog={vi.fn().mockResolvedValue(sampleCatalog)}
        onFetchSkusForCode={noopSkus}
        onExport={noopExport}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("dashboard-error")).toBeInTheDocument();
    });

    expect(screen.getByText("Report not ready")).toBeInTheDocument();
  });
});
