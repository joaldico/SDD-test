/**
 * Ingestion API client (T-3.9).
 *
 * All requests are relative to /api/v1 — nginx proxies this to the FastAPI
 * backend in production; vite dev-server proxies it locally.
 */

import type {
  FileRole,
  MappingItem,
  MappingResponse,
  PreviewResponse,
  RunResponse,
  SourceFileResponse,
} from "../types/ingestion";

const BASE = "/api/v1";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

/** POST /runs — create a new reconciliation run. */
export async function createRun(): Promise<RunResponse> {
  const res = await fetch(`${BASE}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ marketplace: "amazon_es" }),
  });
  if (!res.ok) await parseError(res, `createRun failed: ${res.status}`);
  return res.json() as Promise<RunResponse>;
}

/** POST /runs/{runId}/files — upload a source file with a role. */
export async function uploadFile(
  runId: number,
  role: FileRole,
  file: File
): Promise<SourceFileResponse> {
  const form = new FormData();
  form.append("role", role);
  form.append("file", file);
  const res = await fetch(`${BASE}/runs/${runId}/files`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) await parseError(res, `uploadFile failed: ${res.status}`);
  return res.json() as Promise<SourceFileResponse>;
}

/** GET /runs/{runId}/files/{fileId}/preview — parse & preview with suggestions. */
export async function getPreview(
  runId: number,
  fileId: number,
  sheet?: string
): Promise<PreviewResponse> {
  const url = new URL(
    `${BASE}/runs/${runId}/files/${fileId}/preview`,
    typeof window !== "undefined" ? window.location.origin : "http://localhost"
  );
  if (sheet) url.searchParams.set("sheet", sheet);
  const res = await fetch(url.toString());
  if (!res.ok) await parseError(res, `getPreview failed: ${res.status}`);
  return res.json() as Promise<PreviewResponse>;
}

/** PUT /runs/{runId}/files/{fileId}/mapping — confirm column mapping. */
export async function confirmMapping(
  runId: number,
  fileId: number,
  mappings: MappingItem[]
): Promise<MappingResponse> {
  const res = await fetch(
    `${BASE}/runs/${runId}/files/${fileId}/mapping`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mappings }),
    }
  );
  if (!res.ok) await parseError(res, `confirmMapping failed: ${res.status}`);
  return res.json() as Promise<MappingResponse>;
}
