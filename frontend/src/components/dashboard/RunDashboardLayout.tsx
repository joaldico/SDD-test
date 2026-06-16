/**
 * RunDashboardLayout — base shell for the reconciliation report dashboard (T-5.1).
 *
 * Renders the three primary KPI cards requested for the dashboard shell:
 * Total SKUs, Errores and Desincronizados.
 */

import type { JSX } from "react";
import { SummaryMetricCard } from "./SummaryMetricCard";
import type { RunMetricsResponse } from "../../types/reporting";

interface Props {
  runId: number;
  metrics: RunMetricsResponse;
}

export function RunDashboardLayout({ runId, metrics }: Props): JSX.Element {
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

      <p style={styles.placeholder}>
        Las vistas detalladas por familia, SKU y salud del catálogo se añadirán
        en las siguientes tareas del hito M5.
      </p>
    </div>
  );
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "24px",
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
  placeholder: {
    fontSize: "13px",
    color: "var(--color-text-muted)",
    margin: 0,
    padding: "16px",
    backgroundColor: "var(--color-primary-light)",
    borderRadius: "var(--radius-md)",
  },
} as const;
