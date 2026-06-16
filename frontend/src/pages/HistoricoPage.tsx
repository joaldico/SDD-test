/**
 * HistoricoPage — T-5.5 paginated list of past reconciliation runs (RF-13).
 */

import { useEffect, useState, type JSX } from "react";
import { Link } from "react-router-dom";

import { listRuns } from "../api/reporting";
import type { RunHistoryItem } from "../types/reporting";

type ScreenState =
  | { kind: "loading" }
  | { kind: "ready"; items: RunHistoryItem[]; total: number; page: number; size: number }
  | { kind: "error"; message: string };

const STATUS_LABELS: Record<string, string> = {
  completed: "Completada",
  failed: "Fallida",
  processing: "Procesando",
  mapping: "Mapeo",
  uploaded: "Subida",
};

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-ES", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

export function HistoricoPage(): JSX.Element {
  const [screen, setScreen] = useState<ScreenState>({ kind: "loading" });
  const [page, setPage] = useState(1);
  const pageSize = 20;

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setScreen({ kind: "loading" });
      try {
        const data = await listRuns({ page, size: pageSize });
        if (!cancelled) {
          setScreen({
            kind: "ready",
            items: data.items,
            total: data.total,
            page: data.page,
            size: data.size,
          });
        }
      } catch (err) {
        if (!cancelled) {
          const message =
            err instanceof Error ? err.message : "No se pudo cargar el histórico";
          setScreen({ kind: "error", message });
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [page]);

  if (screen.kind === "loading") {
    return (
      <div style={styles.page}>
        <p role="status">Cargando histórico…</p>
      </div>
    );
  }

  if (screen.kind === "error") {
    return (
      <div style={styles.page}>
        <p role="alert">{screen.message}</p>
      </div>
    );
  }

  const totalPages = Math.max(1, Math.ceil(screen.total / screen.size));

  return (
    <div style={styles.page}>
      <header style={styles.header}>
        <h1 style={styles.title}>Histórico de ejecuciones</h1>
        <p style={styles.subtitle}>
          Consulta ejecuciones anteriores y reabre su informe de conciliación.
        </p>
      </header>

      {screen.items.length === 0 ? (
        <p>No hay ejecuciones registradas todavía.</p>
      ) : (
        <ul style={styles.list}>
          {screen.items.map((run) => {
            const skus = run.summary_metrics?.total_skus;
            const errors = run.summary_metrics?.total_errors;
            const metricsLine =
              skus !== undefined
                ? `${skus} SKUs · ${errors ?? 0} errores`
                : null;

            return (
              <li key={run.id} style={styles.card}>
                <div style={styles.cardMain}>
                  <strong>Ejecución #{run.id}</strong>
                  <span style={styles.badge}>{STATUS_LABELS[run.status] ?? run.status}</span>
                  <div style={styles.meta}>
                    <span>Creada: {formatDate(run.created_at)}</span>
                    {run.completed_at && (
                      <span> · Finalizada: {formatDate(run.completed_at)}</span>
                    )}
                  </div>
                  {metricsLine && <div style={styles.metrics}>{metricsLine}</div>}
                </div>
                <div style={styles.actions}>
                  {run.status === "completed" ? (
                    <Link
                      to={`/historico/${run.id}/informe`}
                      style={styles.linkButton}
                      aria-label={`Ver informe de ejecución #${run.id}`}
                    >
                      Ver informe
                    </Link>
                  ) : (
                    <span style={styles.unavailable}>Informe no disponible</span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {screen.total > screen.size && (
        <nav style={styles.pagination} aria-label="Paginación">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Anterior
          </button>
          <span>
            Página {page} de {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Siguiente
          </button>
        </nav>
      )}
    </div>
  );
}

const styles = {
  page: {
    padding: "32px",
    maxWidth: "900px",
    margin: "0 auto",
  },
  header: {
    marginBottom: "24px",
  },
  title: {
    margin: 0,
    fontSize: "24px",
  },
  subtitle: {
    margin: "8px 0 0",
    color: "var(--color-text-secondary)",
  },
  list: {
    listStyle: "none",
    padding: 0,
    margin: 0,
    display: "flex",
    flexDirection: "column" as const,
    gap: "12px",
  },
  card: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "16px",
    padding: "16px 20px",
    backgroundColor: "var(--color-surface)",
    border: "1px solid var(--color-border)",
    borderRadius: "var(--radius-md)",
  },
  cardMain: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "4px",
  },
  badge: {
    display: "inline-block",
    fontSize: "12px",
    padding: "2px 8px",
    borderRadius: "var(--radius-sm)",
    backgroundColor: "var(--color-bg-subtle)",
    width: "fit-content",
  },
  meta: {
    fontSize: "13px",
    color: "var(--color-text-secondary)",
  },
  metrics: {
    fontSize: "13px",
    color: "var(--color-text-primary)",
  },
  actions: {
    flexShrink: 0,
  },
  linkButton: {
    display: "inline-block",
    padding: "8px 16px",
    backgroundColor: "var(--color-primary)",
    color: "#fff",
    borderRadius: "var(--radius-sm)",
    textDecoration: "none",
    fontSize: "14px",
  },
  unavailable: {
    fontSize: "13px",
    color: "var(--color-text-disabled)",
  },
  pagination: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "16px",
    marginTop: "24px",
  },
} as const;
