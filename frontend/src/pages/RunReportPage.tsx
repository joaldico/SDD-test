/**
 * RunReportPage — T-5.5 reopen Step 6 dashboard for a past run (RF-13).
 */

import { useCallback, type JSX } from "react";
import { Link, useParams } from "react-router-dom";

import { Step6Dashboard } from "../components/wizard/steps/Step6Dashboard";
import * as reportingApi from "../api/reporting";

export function RunReportPage(): JSX.Element {
  const { runId: runIdParam } = useParams<{ runId: string }>();
  const runId = Number(runIdParam);

  const onFetchMetrics = useCallback(() => reportingApi.getRunMetrics(runId), [runId]);
  const onFetchFamilies = useCallback(
    () => reportingApi.getFamiliesReport(runId),
    [runId],
  );
  const onFetchCatalog = useCallback(
    () => reportingApi.getCatalogHealth(runId, { page: 1, page_size: 50 }),
    [runId],
  );
  const onFetchSkusForCode = useCallback(
    (familyCode: string, errorCode: string) =>
      reportingApi
        .getSkuDetail(runId, {
          family: familyCode,
          code: errorCode,
          page: 1,
          page_size: 100,
        })
        .then((response) => response.items),
    [runId],
  );
  const onExport = useCallback(
    (format: "xlsx" | "csv") => reportingApi.exportRunReport(runId, format),
    [runId],
  );

  if (!Number.isFinite(runId) || runId <= 0) {
    return (
      <div style={{ padding: "32px" }}>
        <p role="alert">Identificador de ejecución no válido.</p>
        <Link to="/historico">Volver al histórico</Link>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      <div style={styles.backRow}>
        <Link to="/historico" style={styles.backLink}>
          ← Volver al histórico
        </Link>
      </div>
      <Step6Dashboard
        runId={runId}
        onFetchMetrics={onFetchMetrics}
        onFetchFamilies={onFetchFamilies}
        onFetchCatalog={onFetchCatalog}
        onFetchSkusForCode={onFetchSkusForCode}
        onExport={onExport}
      />
    </div>
  );
}

const styles = {
  page: {
    padding: "32px",
    maxWidth: "1100px",
    margin: "0 auto",
  },
  backRow: {
    marginBottom: "16px",
  },
  backLink: {
    color: "var(--color-primary)",
    textDecoration: "none",
    fontSize: "14px",
  },
} as const;
