/**
 * CatalogHealthTable — Detalle del Catálogo (T-5.2 Vista 3).
 */

import { useEffect, useState, type JSX } from "react";
import type {
  CatalogHealthQuery,
  CatalogHealthResponse,
} from "../../types/reporting";
import {
  REPORT_PAGE_SIZE,
  TablePagination,
  totalPagesFromCount,
} from "./TablePagination";

interface Props {
  onFetchCatalog: (query: CatalogHealthQuery) => Promise<CatalogHealthResponse>;
}

const SYNC_LABELS: Record<string, string> = {
  SENT_WITH_ERROR: "Enviado con error",
  SENT_OK: "Enviado OK",
  NOT_SENT: "No enviado",
  DESYNC_FEED_ONLY: "Desync feed",
  DESYNC_AMAZON_ONLY: "Desync Amazon",
};

const numberFmt = new Intl.NumberFormat("es-ES");

export function CatalogHealthTable({ onFetchCatalog }: Props): JSX.Element {
  const [page, setPage] = useState(1);
  const [catalog, setCatalog] = useState<CatalogHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await onFetchCatalog({ page, page_size: REPORT_PAGE_SIZE });
        if (!cancelled) {
          setCatalog(data);
        }
      } catch (err) {
        if (!cancelled) {
          const message =
            err instanceof Error ? err.message : "No se pudo cargar el catálogo";
          setError(message);
          setCatalog(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [onFetchCatalog, page]);

  const totalPages = catalog
    ? totalPagesFromCount(catalog.total, catalog.page_size)
    : 1;

  return (
    <section aria-label="Detalle del Catálogo" style={styles.section}>
      <div style={styles.headerRow}>
        <h3 style={styles.heading}>Detalle del Catálogo</h3>
        {catalog ? (
          <span style={styles.meta} data-testid="catalog-total">
            {numberFmt.format(catalog.total)} SKUs · priorizados por estado, conflictos y stock
          </span>
        ) : null}
      </div>

      {loading ? (
        <p style={styles.muted} data-testid="catalog-loading">
          Cargando catálogo…
        </p>
      ) : null}

      {error ? (
        <p style={styles.error} role="alert" data-testid="catalog-error">
          {error}
        </p>
      ) : null}

      {!loading && !error && catalog && catalog.items.length === 0 ? (
        <p style={styles.empty} data-testid="catalog-empty">
          No hay SKUs que mostrar con los filtros actuales.
        </p>
      ) : null}

      {!loading && !error && catalog && catalog.items.length > 0 ? (
        <>
          <div style={styles.tableWrap}>
            <table style={styles.table} data-testid="catalog-table">
              <thead>
                <tr>
                  <th style={styles.th}>SKU</th>
                  <th style={styles.th}>Estado</th>
                  <th style={styles.thRight}>Stock feed</th>
                  <th style={styles.thRight}>Stock OCC</th>
                  <th style={styles.th}>Conflictos</th>
                </tr>
              </thead>
              <tbody>
                {catalog.items.map((item) => (
                  <tr
                    key={item.sku_norm}
                    data-testid={`catalog-row-${item.sku_norm}`}
                  >
                    <td style={styles.td}>
                      <span style={styles.sku}>{item.sku_raw}</span>
                    </td>
                    <td style={styles.td}>
                      <span style={styles.badge(item.sync_status)}>
                        {SYNC_LABELS[item.sync_status] ?? item.sync_status}
                      </span>
                    </td>
                    <td style={styles.tdRight}>
                      {item.feed_stock ?? "—"}
                    </td>
                    <td style={styles.tdRight}>
                      {item.occ_stock ?? "—"}
                    </td>
                    <td style={styles.td}>
                      {item.stock_conflict ? (
                        <span style={styles.conflictBadge} data-testid="stock-conflict-badge">
                          Conflicto de stock
                        </span>
                      ) : (
                        <span style={styles.muted}>—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <TablePagination
            page={page}
            totalPages={totalPages}
            onPrevious={() => setPage((current) => Math.max(1, current - 1))}
            onNext={() => setPage((current) => Math.min(totalPages, current + 1))}
            testId="catalog-pagination"
          />
        </>
      ) : null}
    </section>
  );
}

const styles = {
  section: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "12px",
  },
  headerRow: {
    display: "flex",
    flexWrap: "wrap" as const,
    alignItems: "baseline",
    justifyContent: "space-between",
    gap: "8px",
  },
  heading: {
    fontSize: "16px",
    fontWeight: 600,
    margin: 0,
    color: "var(--color-text)",
  },
  meta: {
    fontSize: "12px",
    color: "var(--color-text-muted)",
  },
  empty: {
    margin: 0,
    fontSize: "13px",
    color: "var(--color-text-muted)",
  },
  muted: {
    margin: 0,
    fontSize: "13px",
    color: "var(--color-text-muted)",
  },
  error: {
    margin: 0,
    fontSize: "13px",
    color: "#dc2626",
  },
  tableWrap: {
    overflowX: "auto" as const,
    border: "1px solid var(--color-border)",
    borderRadius: "var(--radius-md)",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse" as const,
    fontSize: "13px",
  },
  th: {
    textAlign: "left" as const,
    padding: "10px 12px",
    backgroundColor: "var(--color-primary-light)",
    borderBottom: "1px solid var(--color-border)",
    fontWeight: 600,
  },
  thRight: {
    textAlign: "right" as const,
    padding: "10px 12px",
    backgroundColor: "var(--color-primary-light)",
    borderBottom: "1px solid var(--color-border)",
    fontWeight: 600,
  },
  td: {
    padding: "10px 12px",
    borderBottom: "1px solid var(--color-border)",
    verticalAlign: "middle" as const,
  },
  tdRight: {
    padding: "10px 12px",
    borderBottom: "1px solid var(--color-border)",
    textAlign: "right" as const,
    verticalAlign: "middle" as const,
  },
  sku: {
    fontFamily: "monospace",
    fontSize: "12px",
  },
  badge: (syncStatus: string) => ({
    display: "inline-block",
    padding: "2px 8px",
    borderRadius: "999px",
    fontSize: "11px",
    fontWeight: 600,
    backgroundColor:
      syncStatus === "SENT_WITH_ERROR"
        ? "#fee2e2"
        : syncStatus === "NOT_SENT" || syncStatus.startsWith("DESYNC")
          ? "#ffedd5"
          : "#ecfdf5",
    color:
      syncStatus === "SENT_WITH_ERROR"
        ? "#991b1b"
        : syncStatus === "NOT_SENT" || syncStatus.startsWith("DESYNC")
          ? "#9a3412"
          : "#065f46",
  }),
  conflictBadge: {
    display: "inline-block",
    padding: "2px 8px",
    borderRadius: "999px",
    fontSize: "11px",
    fontWeight: 600,
    backgroundColor: "#ede9fe",
    color: "#5b21b6",
  },
} as const;
