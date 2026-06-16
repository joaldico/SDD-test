/**
 * MetricsBreakdownPanel — sync_status breakdown tab (T-5.4).
 */

import type { JSX } from "react";
import { SummaryMetricCard } from "./SummaryMetricCard";
import type { RunMetricsResponse } from "../../types/reporting";

interface Props {
  metrics: RunMetricsResponse;
}

const STATUS_ROWS: {
  key: keyof RunMetricsResponse["by_sync_status"];
  label: string;
  color: string;
}[] = [
  { key: "sent_with_error", label: "Enviados con error", color: "#dc2626" },
  { key: "sent_ok", label: "Enviados sin error", color: "#16a34a" },
  { key: "not_sent", label: "No enviados", color: "#92400e" },
  { key: "desync_feed_only", label: "Solo en feed", color: "#7c3aed" },
  { key: "desync_amazon_only", label: "Solo en Amazon", color: "#0891b2" },
];

const numberFmt = new Intl.NumberFormat("es-ES");

export function MetricsBreakdownPanel({ metrics }: Props): JSX.Element {
  const { summary, by_sync_status: breakdown } = metrics;

  return (
    <section aria-label="Métricas de conciliación" style={styles.section}>
      <h3 style={styles.heading}>Métricas de conciliación</h3>
      <p style={styles.subtitle}>
        Desglose por estado de sincronización y resumen global del run.
      </p>

      <div style={styles.summaryGrid}>
        <SummaryMetricCard
          label="Total SKUs"
          value={summary.total_skus}
          color="#1d4ed8"
          testId="metrics-tab-total-skus"
        />
        <SummaryMetricCard
          label="Errores"
          value={summary.total_errors}
          color="#dc2626"
          testId="metrics-tab-total-errors"
        />
        <SummaryMetricCard
          label="Desincronizados"
          value={summary.desynchronized}
          color="#7c3aed"
          testId="metrics-tab-desynchronized"
        />
      </div>

      <div style={styles.tableWrap}>
        <table style={styles.table} data-testid="metrics-breakdown-table">
          <thead>
            <tr>
              <th style={styles.th}>Estado</th>
              <th style={styles.thRight}>SKUs</th>
              <th style={styles.thRight}>% del total</th>
            </tr>
          </thead>
          <tbody>
            {STATUS_ROWS.map((row) => {
              const value = breakdown[row.key];
              const pct =
                summary.total_skus > 0
                  ? ((value / summary.total_skus) * 100).toFixed(1)
                  : "0.0";
              return (
                <tr key={row.key} data-testid={`metrics-row-${row.key}`}>
                  <td style={styles.td}>
                    <span style={styles.statusDot(row.color)} aria-hidden />
                    {row.label}
                  </td>
                  <td style={styles.tdRight}>{numberFmt.format(value)}</td>
                  <td style={styles.tdRight}>{pct}%</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const styles = {
  section: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "16px",
  },
  heading: {
    fontSize: "16px",
    fontWeight: 600,
    margin: 0,
    color: "var(--color-text)",
  },
  subtitle: {
    fontSize: "13px",
    color: "var(--color-text-muted)",
    margin: 0,
  },
  summaryGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
    gap: "12px",
  },
  tableWrap: {
    overflowX: "auto" as const,
    border: "1px solid var(--color-border)",
    borderRadius: "var(--radius-md)",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse" as const,
    fontSize: "13px",
  },
  th: {
    textAlign: "left" as const,
    padding: "10px 12px",
    backgroundColor: "var(--color-primary-light)",
    borderBottom: "1px solid var(--color-border)",
    fontWeight: 600,
  },
  thRight: {
    textAlign: "right" as const,
    padding: "10px 12px",
    backgroundColor: "var(--color-primary-light)",
    borderBottom: "1px solid var(--color-border)",
    fontWeight: 600,
  },
  td: {
    padding: "10px 12px",
    borderBottom: "1px solid var(--color-border)",
    verticalAlign: "middle" as const,
  },
  tdRight: {
    padding: "10px 12px",
    borderBottom: "1px solid var(--color-border)",
    textAlign: "right" as const,
    verticalAlign: "middle" as const,
  },
  statusDot: (color: string) => ({
    display: "inline-block",
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    backgroundColor: color,
    marginRight: "8px",
  }),
} as const;
