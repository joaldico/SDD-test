/**
 * RunDashboardLayout — render tests (T-5.1 / T-5.2).
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import { RunDashboardLayout } from "../../components/dashboard/RunDashboardLayout";
import type {
  CatalogHealthResponse,
  FamiliesReportResponse,
  RunMetricsResponse,
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

describe("RunDashboardLayout", () => {
  it("renders summary cards and detail tables", async () => {
    const user = userEvent.setup();

    render(
      <RunDashboardLayout
        runId={42}
        metrics={sampleMetrics}
        families={sampleFamilies}
        catalog={sampleCatalog}
      />,
    );

    expect(screen.getByTestId("run-dashboard")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-total-skus")).toHaveTextContent("4,094");
    expect(screen.getByTestId("dashboard-total-errors")).toHaveTextContent("845");
    expect(screen.getByTestId("dashboard-desynchronized")).toHaveTextContent("66");

    expect(screen.getByText("Top de Errores por Familia")).toBeInTheDocument();
    expect(screen.getByTestId("families-table")).toBeInTheDocument();
    expect(screen.getByTestId("family-row-AUTORIZACION_MARCA")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Autorización de marca" }));
    expect(screen.getByTestId("family-codes-AUTORIZACION_MARCA")).toHaveTextContent("18299");

    expect(screen.getByText("Detalle del Catálogo")).toBeInTheDocument();
    expect(screen.getByTestId("catalog-table")).toBeInTheDocument();
    expect(screen.getByTestId("catalog-row-SKU-A")).toBeInTheDocument();
    expect(screen.getByTestId("stock-conflict-badge")).toBeInTheDocument();
  });
});
