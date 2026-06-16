/**
 * Step6Dashboard — T-5.1 / T-5.4 report dashboard (wizard step 6).
 *
 * Fetches metrics, families report and catalog health for the completed run.
 */

import { useEffect, useState, type JSX } from "react";
import { RunDashboardLayout } from "../../dashboard/RunDashboardLayout";
import type {
  CatalogHealthResponse,
  ExportFormat,
  FamiliesReportResponse,
  RunMetricsResponse,
  SkuDetailItem,
} from "../../../types/reporting";

interface Props {
  runId: number;
  onFetchMetrics: () => Promise<RunMetricsResponse>;
  onFetchFamilies: () => Promise<FamiliesReportResponse>;
  onFetchCatalog: () => Promise<CatalogHealthResponse>;
  onFetchSkusForCode: (
    familyCode: string,
    errorCode: string,
  ) => Promise<SkuDetailItem[]>;
  onExport: (format: ExportFormat) => Promise<void>;
  onBack?: () => void;
}

type ScreenState =
  | { kind: "loading" }
  | {
      kind: "ready";
      metrics: RunMetricsResponse;
      families: FamiliesReportResponse;
      catalog: CatalogHealthResponse;
    }
  | { kind: "error"; message: string };

export function Step6Dashboard({
  runId,
  onFetchMetrics,
  onFetchFamilies,
  onFetchCatalog,
  onFetchSkusForCode,
  onExport,
  onBack,
}: Props): JSX.Element {
  const [screen, setScreen] = useState<ScreenState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const [metrics, families, catalog] = await Promise.all([
          onFetchMetrics(),
          onFetchFamilies(),
          onFetchCatalog(),
        ]);
        if (!cancelled) {
          setScreen({ kind: "ready", metrics, families, catalog });
        }
      } catch (err) {
        if (!cancelled) {
          const message =
            err instanceof Error ? err.message : "No se pudo cargar el informe";
          setScreen({ kind: "error", message });
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [onFetchMetrics, onFetchFamilies, onFetchCatalog]);

  if (screen.kind === "loading") {
    return (
      <div style={styles.centered} data-testid="dashboard-loading">
        <div style={styles.spinner} role="status" aria-label="Cargando informe" />
        <p style={styles.loadingText}>Cargando informe de la conciliación…</p>
      </div>
    );
  }

  if (screen.kind === "error") {
    return (
      <div style={styles.centered} data-testid="dashboard-error">
        <p style={styles.errorText}>{screen.message}</p>
        {onBack ? (
          <button type="button" style={styles.backButton} onClick={onBack}>
            Volver
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <div data-testid="step6-dashboard">
      <RunDashboardLayout
        runId={runId}
        metrics={screen.metrics}
        families={screen.families}
        catalog={screen.catalog}
        onFetchSkusForCode={onFetchSkusForCode}
        onExport={onExport}
      />
      {onBack ? (
        <div style={styles.footer}>
          <button type="button" style={styles.backButton} onClick={onBack}>
            Volver al progreso
          </button>
        </div>
      ) : null}
    </div>
  );
}

const styles = {
  centered: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    justifyContent: "center",
    gap: "16px",
    minHeight: "240px",
  },
  spinner: {
    width: "36px",
    height: "36px",
    border: "3px solid var(--color-border)",
    borderTopColor: "var(--color-primary)",
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
  },
  loadingText: {
    fontSize: "14px",
    color: "var(--color-text-muted)",
    margin: 0,
  },
  errorText: {
    fontSize: "14px",
    color: "#dc2626",
    margin: 0,
    textAlign: "center" as const,
  },
  footer: {
    marginTop: "24px",
    display: "flex",
    justifyContent: "flex-start",
  },
  backButton: {
    padding: "8px 16px",
    fontSize: "13px",
    borderRadius: "var(--radius-md)",
    border: "1px solid var(--color-border)",
    backgroundColor: "var(--color-surface)",
    color: "var(--color-text)",
    cursor: "pointer",
  },
} as const;
