/**
 * RunDashboardLayout — render tests (T-5.1 / T-5.4).
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { RunDashboardLayout } from "../../components/dashboard/RunDashboardLayout";
import type {
  CatalogHealthResponse,
  FamiliesReportResponse,
  RunMetricsResponse,
  SkuDetailResponse,
} from "../../types/reporting";

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

const sampleFamilies: FamiliesReportResponse = {
  run_id: 42,
  sin_clasificar_warning: false,
  families: [
    {
      code: "AUTORIZACION_MARCA",
      display_name: "Autorización de marca",
      unique_skus: 950,
      total_errors: 1904,
      codes: [
        { code: "18299", message: "Marca no autorizada", count: 1786 },
        { code: "18749", message: "Uso indebido de marca", count: 118 },
      ],
    },
  ],
};

const sampleCatalog: CatalogHealthResponse = {
  run_id: 42,
  total: 2,
  page: 1,
  page_size: 50,
  items: [
    {
      sku_norm: "SKU-A",
      sku_raw: "SKU-A",
      sync_status: "DESYNC_FEED_ONLY",
      feed_stock: 100,
      occ_stock: null,
      stock_conflict: true,
      in_occ: false,
      in_feed: true,
      in_amazon_report: false,
      stock_disponible: true,
    },
    {
      sku_norm: "SKU-B",
      sku_raw: "SKU-B",
      sync_status: "NOT_SENT",
      feed_stock: null,
      occ_stock: 5,
      stock_conflict: false,
      in_occ: true,
      in_feed: false,
      in_amazon_report: false,
      stock_disponible: false,
    },
  ],
};

const sampleSkus: SkuDetailResponse = {
  run_id: 42,
  family_code: "AUTORIZACION_MARCA",
  error_code: "18299",
  total: 1,
  page: 1,
  page_size: 50,
  items: [
    {
      sku_raw: "TWA85XL",
      sku_norm: "TWA85XL",
      error_code: "18299",
      error_category: "ERROR",
      error_message: "Marca no autorizada",
      affected_field: "brand",
    },
  ],
};

describe("RunDashboardLayout", () => {
  it("renders KPI cards, export buttons and tabbed report views", async () => {
    const user = userEvent.setup();
    const onFetchCatalog = vi.fn().mockResolvedValue(sampleCatalog);
    const onFetchSkusForCode = vi.fn().mockResolvedValue(sampleSkus);
    const onExport = vi.fn().mockResolvedValue(undefined);

    render(
      <RunDashboardLayout
        runId={42}
        metrics={sampleMetrics}
        families={sampleFamilies}
        onFetchCatalog={onFetchCatalog}
        onFetchSkusForCode={onFetchSkusForCode}
        onExport={onExport}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("catalog-table")).toBeInTheDocument();
    });
    expect(onFetchCatalog).toHaveBeenCalledWith({ page: 1, page_size: 50 });

    expect(screen.getByTestId("run-dashboard")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-total-skus")).toHaveTextContent("4,094");
    expect(screen.getByTestId("export-xlsx-button")).toBeInTheDocument();
    expect(screen.getByTestId("export-csv-button")).toBeInTheDocument();

    expect(screen.getByTestId("dashboard-tab-catalog")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-tab-families")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-tab-metrics")).toBeInTheDocument();

    expect(screen.getByTestId("dashboard-panel-catalog")).toBeVisible();
    expect(screen.getByTestId("catalog-table")).toBeInTheDocument();

    await user.click(screen.getByTestId("dashboard-tab-families"));
    expect(screen.getByTestId("dashboard-panel-families")).toBeVisible();
    expect(screen.getByTestId("families-table")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: /Autorización de marca/ }),
    );
    expect(screen.getByTestId("family-codes-AUTORIZACION_MARCA")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /18299/ }));
    await waitFor(() => {
      expect(onFetchSkusForCode).toHaveBeenCalledWith("AUTORIZACION_MARCA", "18299", 1);
    });
    expect(screen.getByTestId("sku-list-AUTORIZACION_MARCA-18299")).toHaveTextContent(
      "TWA85XL",
    );

    await user.click(screen.getByTestId("dashboard-tab-metrics"));
    expect(screen.getByTestId("dashboard-panel-metrics")).toBeVisible();
    expect(screen.getByTestId("metrics-breakdown-table")).toBeInTheDocument();

    await user.click(screen.getByTestId("export-xlsx-button"));
    expect(onExport).toHaveBeenCalledWith("xlsx");
  });
});
