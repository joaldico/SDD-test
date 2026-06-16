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
