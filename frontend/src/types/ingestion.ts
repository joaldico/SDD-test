/**
 * TypeScript interfaces for the ingestion API contracts (T-3.9).
 * Mirrors the Pydantic response models in backend/src/marketplace_conciliator/ingestion/router.py
 */

export type FileRole = "occ_top" | "wm_feed" | "amazon_report";

/** Human-readable labels per role */
export const ROLE_LABELS: Record<FileRole, string> = {
  occ_top: "OCC Top Ventas (.xlsx)",
  wm_feed: "Wavemarket Feed (.csv / .txt)",
  amazon_report: "Amazon Processing Summary (.xlsm)",
};

/** Mandatory logical fields per file role (frontend gate — RNF-08) */
export const REQUIRED_FIELDS: Record<FileRole, string[]> = {
  occ_top: ["sku", "stock"],
  wm_feed: ["sku", "stock"],
  amazon_report: ["sku"],
};

/** Human-readable labels per logical field */
export const FIELD_LABELS: Record<string, string> = {
  sku: "SKU / Referencia",
  stock: "Stock / Cantidad",
};

// ---------------------------------------------------------------------------
// Run
// ---------------------------------------------------------------------------

export interface RunResponse {
  id: number;
  user_id: number;
  marketplace: string;
  status: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Source file (upload)
// ---------------------------------------------------------------------------

export interface SourceFileResponse {
  id: number;
  run_id: number;
  role: string;
  original_filename: string;
  sha256: string;
  total_rows: number;
  discarded_rows: number;
  uploaded_at: string;
}

// ---------------------------------------------------------------------------
// Preview
// ---------------------------------------------------------------------------

export interface SheetInfo {
  name: string;
  rows: number;
}

export interface BlockInfo {
  title_matched: string;
  header_row: number;
  data_start_row: number;
}

export interface HeaderInfo {
  index: number;
  name: string;
  technical_name: string | null;
}

export interface ColumnSuggestion {
  column_index: number;
  confidence: number;
  reason: string;
}

export interface PreviewWarning {
  code: string;
  message: string;
  row: number | null;
}

export interface PreviewResponse {
  file_role: string;
  sheet: string | null;
  available_sheets: SheetInfo[] | null;
  block: BlockInfo | null;
  headers: HeaderInfo[];
  sample_rows: string[][];
  suggestions: Record<string, ColumnSuggestion>;
  remembered_mappings?: Record<string, RememberedMapping>;
  warnings: PreviewWarning[];
  discarded_rows: number;
}

export interface RememberedMapping {
  column_index: number;
  from_run_id: number;
  reason: string;
}

// ---------------------------------------------------------------------------
// Mapping
// ---------------------------------------------------------------------------

export interface MappingItem {
  logical_field: string;
  column_index: number;
  was_suggested: boolean;
}

export interface MappingWarning {
  code: string;
  message: string;
  sample: string[] | null;
}

export interface MappingResponse {
  status: "ok" | "warnings";
  warnings: MappingWarning[];
}

// ---------------------------------------------------------------------------
// Process / Status (T-4.6)
// ---------------------------------------------------------------------------

export interface ProcessResponse {
  status_url: string;
}

export type RunStatusValue =
  | "uploaded"
  | "mapping"
  | "processing"
  | "completed"
  | "failed";

export interface SummaryMetrics {
  total_skus: number;
  sent_with_error: number;
  sent_ok: number;
  not_sent: number;
  desync_feed_only: number;
  desync_amazon_only: number;
  total_errors: number;
}

/** Response for GET /runs/{id}/status — ADR-002 polling contract */
export interface RunStatusResponse {
  status: RunStatusValue;
  phase: string | null;
  failure_reason: string | null;
  summary_metrics: SummaryMetrics | null;
}
