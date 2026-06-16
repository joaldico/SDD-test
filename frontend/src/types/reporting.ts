/** Types for GET /runs/{id}/metrics — T-5.1 dashboard shell */

export interface DashboardSummary {
  total_skus: number;
  total_errors: number;
  desynchronized: number;
}

export interface SyncStatusBreakdown {
  sent_with_error: number;
  sent_ok: number;
  not_sent: number;
  desync_feed_only: number;
  desync_amazon_only: number;
}

export interface RunMetricsResponse {
  run_id: number;
  status: string;
  completed_at: string | null;
  summary: DashboardSummary;
  by_sync_status: SyncStatusBreakdown;
}

/** Types for GET /runs/{id}/report/families — T-5.2 Vista 1 */

export interface ErrorCodeBreakdown {
  code: string;
  message: string;
  count: number;
}

export interface FamilyBreakdown {
  code: string;
  display_name: string;
  unique_skus: number;
  total_errors: number;
  codes: ErrorCodeBreakdown[];
}

export interface FamiliesReportResponse {
  run_id: number;
  families: FamilyBreakdown[];
  sin_clasificar_warning: boolean;
}

/** Types for GET /runs/{id}/catalog-health — T-5.2 Vista 3 */

export interface CatalogHealthItem {
  sku_norm: string;
  sku_raw: string;
  sync_status: string;
  feed_stock: number | null;
  occ_stock: number | null;
  stock_conflict: boolean;
  in_occ: boolean;
  in_feed: boolean;
  in_amazon_report: boolean;
  stock_disponible: boolean;
}

export interface CatalogHealthResponse {
  run_id: number;
  items: CatalogHealthItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface CatalogHealthQuery {
  sync_status?: string;
  page?: number;
  page_size?: number;
}
