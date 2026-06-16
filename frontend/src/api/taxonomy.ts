/**
 * Taxonomy admin API client (T-5.6, RF-14).
 */

import type {
  ErrorCodeResponse,
  ErrorTaxonomyResponse,
  PatchErrorCodeRequest,
} from "../types/taxonomy";

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

/** GET /error-families — full taxonomy catalog. */
export async function getErrorTaxonomy(): Promise<ErrorTaxonomyResponse> {
  const res = await fetch(`${BASE}/error-families`);
  if (!res.ok) await parseError(res, `getErrorTaxonomy failed: ${res.status}`);
  return res.json() as Promise<ErrorTaxonomyResponse>;
}

/** PATCH /error-codes/{code} — reassign code to a family (admin only). */
export async function patchErrorCodeFamily(
  code: string,
  body: PatchErrorCodeRequest,
): Promise<ErrorCodeResponse> {
  const res = await fetch(`${BASE}/error-codes/${encodeURIComponent(code)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) await parseError(res, `patchErrorCodeFamily failed: ${res.status}`);
  return res.json() as Promise<ErrorCodeResponse>;
}
