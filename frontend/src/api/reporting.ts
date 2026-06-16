/**
 * Reporting API client (T-5.1 / T-5.2).
 */

import type {
  CatalogHealthQuery,
  CatalogHealthResponse,
  FamiliesReportResponse,
  RunMetricsResponse,
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
