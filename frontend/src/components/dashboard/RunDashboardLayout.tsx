/**
 * RunDashboardLayout — base shell for the reconciliation report dashboard (T-5.1 / T-5.2).
 *
 * Renders KPI cards plus Vista 1 (familias) and Vista 3 (catálogo).
 */

import type { JSX } from "react";
import { CatalogHealthTable } from "./CatalogHealthTable";
import { FamilyErrorsTable } from "./FamilyErrorsTable";
import { SummaryMetricCard } from "./SummaryMetricCard";
import type {
  CatalogHealthResponse,
  FamiliesReportResponse,
  RunMetricsResponse,
} from "../../types/reporting";

interface Props {
  runId: number;
  metrics: RunMetricsResponse;
  families: FamiliesReportResponse;
  catalog: CatalogHealthResponse;
}

export function RunDashboardLayout({
  runId,
  metrics,
  families,
  catalog,
}: Props): JSX.Element {
  const { summary } = metrics;

  return (
    <div style={styles.container} data-testid="run-dashboard">
      <header style={styles.header}>
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

      <FamilyErrorsTable report={families} />
      <CatalogHealthTable catalog={catalog} />
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
    gap: "6px",
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
    margin: 0,
  },
  summaryGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "16px",
  },
} as const;
