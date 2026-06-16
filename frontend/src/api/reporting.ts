/**
 * Reporting API client (T-5.1 / T-5.2).
 */

import type {
  CatalogHealthQuery,
  CatalogHealthResponse,
  ExportFormat,
  FamiliesReportResponse,
  RunHistoryListResponse,
  RunHistoryQuery,
  RunMetricsResponse,
  SkuDetailQuery,
  SkuDetailResponse,
} from "../types/reporting";

const BASE = "/api/v1";

async function parseError(res: Response, fallback: string): Promise<never> {
  let detail = fallback;
  try {
    const body = (await res.json()) as { detail?: string };
    if (typeof body.detail === "string") detail = body.detail;
  } catch {
    // ignore parse failure
  }
  throw new Error(detail);
}

/** GET /runs — paginated reconciliation run history (T-5.5, RF-13). */
export async function listRuns(
  query: RunHistoryQuery = {},
): Promise<RunHistoryListResponse> {
  const params = new URLSearchParams();
  if (query.page !== undefined) params.set("page", String(query.page));
  if (query.size !== undefined) params.set("size", String(query.size));
  if (query.status) params.set("status", query.status);

  const qs = params.toString();
  const url = `${BASE}/runs${qs ? `?${qs}` : ""}`;
  const res = await fetch(url);
  if (!res.ok) await parseError(res, `listRuns failed: ${res.status}`);
  return res.json() as Promise<RunHistoryListResponse>;
}

/** GET /runs/{runId}/metrics — dashboard KPIs for a completed run. */
export async function getRunMetrics(runId: number): Promise<RunMetricsResponse> {
  const res = await fetch(`${BASE}/runs/${runId}/metrics`);
  if (!res.ok) await parseError(res, `getRunMetrics failed: ${res.status}`);
  return res.json() as Promise<RunMetricsResponse>;
}

/** GET /runs/{runId}/report/families — Vista 1 error aggregation. */
export async function getFamiliesReport(
  runId: number,
): Promise<FamiliesReportResponse> {
  const res = await fetch(`${BASE}/runs/${runId}/report/families`);
  if (!res.ok) await parseError(res, `getFamiliesReport failed: ${res.status}`);
  return res.json() as Promise<FamiliesReportResponse>;
}

/** GET /runs/{runId}/catalog-health — Vista 3 catalog sync detail. */
export async function getCatalogHealth(
  runId: number,
  query: CatalogHealthQuery = {},
): Promise<CatalogHealthResponse> {
  const params = new URLSearchParams();
  if (query.sync_status) params.set("sync_status", query.sync_status);
  if (query.page !== undefined) params.set("page", String(query.page));
  if (query.page_size !== undefined) params.set("page_size", String(query.page_size));

  const qs = params.toString();
  const url = `${BASE}/runs/${runId}/catalog-health${qs ? `?${qs}` : ""}`;
  const res = await fetch(url);
  if (!res.ok) await parseError(res, `getCatalogHealth failed: ${res.status}`);
  return res.json() as Promise<CatalogHealthResponse>;
}

/** GET /runs/{runId}/report/sku-detail — Vista 2 SKU rows for family/code drill-down. */
export async function getSkuDetail(
  runId: number,
  query: SkuDetailQuery = {},
): Promise<SkuDetailResponse> {
  const params = new URLSearchParams();
  if (query.family) params.set("family", query.family);
  if (query.code) params.set("code", query.code);
  if (query.page !== undefined) params.set("page", String(query.page));
  if (query.page_size !== undefined) params.set("page_size", String(query.page_size));

  const qs = params.toString();
  const url = `${BASE}/runs/${runId}/report/sku-detail${qs ? `?${qs}` : ""}`;
  const res = await fetch(url);
  if (!res.ok) await parseError(res, `getSkuDetail failed: ${res.status}`);
  return res.json() as Promise<SkuDetailResponse>;
}

function parseContentDispositionFilename(header: string | null): string | null {
  if (!header) return null;
  const match = /filename="([^"]+)"/.exec(header);
  return match?.[1] ?? null;
}

/** GET /runs/{runId}/export — download xlsx workbook or csv zip archive (T-5.3). */
export async function exportRunReport(
  runId: number,
  format: ExportFormat,
): Promise<void> {
  const res = await fetch(`${BASE}/runs/${runId}/export?format=${format}`);
  if (!res.ok) await parseError(res, `exportRunReport failed: ${res.status}`);

  const blob = await res.blob();
  const fallback =
    format === "xlsx" ? `informe_run_${runId}.xlsx` : `informe_run_${runId}.zip`;
  const filename =
    parseContentDispositionFilename(res.headers.get("Content-Disposition")) ??
    fallback;

  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}
