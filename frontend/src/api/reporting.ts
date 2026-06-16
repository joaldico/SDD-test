/**
 * Reporting API client (T-5.1).
 */

import type { RunMetricsResponse } from "../types/reporting";

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
