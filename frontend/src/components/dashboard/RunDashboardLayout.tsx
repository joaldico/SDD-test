/**
 * RunDashboardLayout — report dashboard with KPI cards, export actions and 3 tabs (T-5.1 / T-5.4).
 */

import { useState, type JSX } from "react";
import { CatalogHealthTable } from "./CatalogHealthTable";
import { DashboardTabs } from "./DashboardTabs";
import { FamilyErrorsTable } from "./FamilyErrorsTable";
import { MetricsBreakdownPanel } from "./MetricsBreakdownPanel";
import { SummaryMetricCard } from "./SummaryMetricCard";
import type {
  CatalogHealthResponse,
  ExportFormat,
  FamiliesReportResponse,
  RunMetricsResponse,
  SkuDetailItem,
} from "../../types/reporting";

interface Props {
  runId: number;
  metrics: RunMetricsResponse;
  families: FamiliesReportResponse;
  catalog: CatalogHealthResponse;
  onFetchSkusForCode: (
    familyCode: string,
    errorCode: string,
  ) => Promise<SkuDetailItem[]>;
  onExport: (format: ExportFormat) => Promise<void>;
}

export function RunDashboardLayout({
  runId,
  metrics,
  families,
  catalog,
  onFetchSkusForCode,
  onExport,
}: Props): JSX.Element {
  const { summary } = metrics;
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const handleExport = async (format: ExportFormat): Promise<void> => {
    setExporting(format);
    setExportError(null);
    try {
      await onExport(format);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "No se pudo exportar el informe";
      setExportError(message);
    } finally {
      setExporting(null);
    }
  };

  return (
    <div style={styles.container} data-testid="run-dashboard">
      <header style={styles.header}>
        <div style={styles.headerMain}>
          <div>
            <h2 style={styles.title}>Informe de conciliación</h2>
            <p style={styles.subtitle}>
              Run <strong>#{runId}</strong>
              {metrics.completed_at ? (
                <>
                  {" "}
                  · completado el{" "}
                  <time dateTime={metrics.completed_at}>
                    {new Date(metrics.completed_at).toLocaleString()}
                  </time>
                </>
              ) : null}
            </p>
          </div>

          <div style={styles.exportActions}>
            <button
              type="button"
              style={styles.exportButton}
              onClick={() => void handleExport("xlsx")}
              disabled={exporting !== null}
              data-testid="export-xlsx-button"
            >
              {exporting === "xlsx" ? "Exportando…" : "Exportar Excel"}
            </button>
            <button
              type="button"
              style={styles.exportButton}
              onClick={() => void handleExport("csv")}
              disabled={exporting !== null}
              data-testid="export-csv-button"
            >
              {exporting === "csv" ? "Exportando…" : "Exportar CSV"}
            </button>
          </div>
        </div>

        {exportError ? (
          <p style={styles.exportError} role="alert" data-testid="export-error">
            {exportError}
          </p>
        ) : null}
      </header>

      <section aria-label="Resumen principal" style={styles.summaryGrid}>
        <SummaryMetricCard
          label="Total SKUs"
          value={summary.total_skus}
          color="#1d4ed8"
          testId="dashboard-total-skus"
        />
        <SummaryMetricCard
          label="Errores"
          value={summary.total_errors}
          color="#dc2626"
          testId="dashboard-total-errors"
        />
        <SummaryMetricCard
          label="Desincronizados"
          value={summary.desynchronized}
          color="#7c3aed"
          testId="dashboard-desynchronized"
        />
      </section>

      <DashboardTabs
        panels={{
          catalog: <CatalogHealthTable catalog={catalog} />,
          families: (
            <FamilyErrorsTable
              report={families}
              onFetchSkusForCode={onFetchSkusForCode}
            />
          ),
          metrics: <MetricsBreakdownPanel metrics={metrics} />,
        }}
      />
    </div>
  );
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "32px",
  },
  header: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "10px",
  },
  headerMain: {
    display: "flex",
    flexWrap: "wrap" as const,
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: "16px",
  },
  title: {
    fontSize: "20px",
    fontWeight: 700,
    color: "var(--color-text)",
    margin: 0,
  },
  subtitle: {
    fontSize: "14px",
    color: "var(--color-text-muted)",
    margin: "6px 0 0",
  },
  exportActions: {
    display: "flex",
    flexWrap: "wrap" as const,
    gap: "8px",
  },
  exportButton: {
    padding: "8px 16px",
    fontSize: "13px",
    fontWeight: 600,
    borderRadius: "var(--radius-md)",
    border: "1px solid var(--color-border)",
    backgroundColor: "var(--color-surface)",
    color: "var(--color-text)",
    cursor: "pointer",
  },
  exportError: {
    margin: 0,
    fontSize: "13px",
    color: "#dc2626",
  },
  summaryGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "16px",
  },
} as const;
