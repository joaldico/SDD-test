/**
 * Step5Progress — T-4.6 Pipeline progress screen.
 *
 * Renders after the user clicks "Procesar" in Step 4.
 * Calls POST /runs/{id}/process once on mount (via onProcess prop),
 * then polls GET /runs/{id}/status every 2 s until the run reaches
 * "completed" or "failed" (plan 3.5, ADR-002).
 *
 * Phases shown (plan 3.4):
 *   Validando → Deduplicando → Cruzando → Persistiendo → Listo
 */

import { useEffect, useRef, useState, type JSX } from "react";
import type { RunStatusResponse, SummaryMetrics } from "../../../types/ingestion";

const POLL_INTERVAL_MS = 2000;

/** Ordered pipeline phases for the progress stepper */
const PIPELINE_PHASES: string[] = [
  "Validando",
  "Deduplicando",
  "Cruzando",
  "Persistiendo",
];

interface Props {
  runId: number;
  /** Called once on mount to POST /runs/{id}/process. Returns the status_url. */
  onProcess: () => Promise<string>;
  /** Called to poll GET /runs/{id}/status. */
  onPollStatus: () => Promise<RunStatusResponse>;
  /** Called when the user opens the dashboard after completion (T-5.1). */
  onViewDashboard?: () => void;
  /** Poll interval in ms. Override in tests to speed up. Default: 2000. */
  pollIntervalMs?: number;
}

type ScreenState =
  | { kind: "submitting" }
  | { kind: "polling"; phase: string | null }
  | { kind: "completed"; metrics: SummaryMetrics }
  | { kind: "failed"; reason: string };

export function Step5Progress({
  runId,
  onProcess,
  onPollStatus,
  onViewDashboard,
  pollIntervalMs = POLL_INTERVAL_MS,
}: Props): JSX.Element {
  const [screen, setScreen] = useState<ScreenState>({ kind: "submitting" });
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const hasStarted = useRef(false);

  const stopPolling = () => {
    if (pollingRef.current !== null) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  useEffect(() => {
    if (hasStarted.current) return;
    hasStarted.current = true;

    let cancelled = false;

    const start = async () => {
      try {
        await onProcess();
      } catch (err) {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : "Error al iniciar el proceso";
          setScreen({ kind: "failed", reason: msg });
        }
        return;
      }

      if (cancelled) return;
      setScreen({ kind: "polling", phase: null });

      pollingRef.current = setInterval(async () => {  // eslint-disable-line @typescript-eslint/no-misused-promises
        if (cancelled) {
          stopPolling();
          return;
        }
        try {
          const status = await onPollStatus();
          if (status.status === "completed") {
            stopPolling();
            setScreen({
              kind: "completed",
              metrics: status.summary_metrics ?? {
                total_skus: 0,
                sent_with_error: 0,
                sent_ok: 0,
                not_sent: 0,
                desync_feed_only: 0,
                desync_amazon_only: 0,
                total_errors: 0,
              },
            });
          } else if (status.status === "failed") {
            stopPolling();
            setScreen({
              kind: "failed",
              reason: status.failure_reason ?? "Error desconocido en el pipeline",
            });
          } else {
            setScreen({ kind: "polling", phase: status.phase });
          }
        } catch {
          // network errors during poll — keep polling (transient)
        }
      }, pollIntervalMs);
    };

    void start();

    return () => {
      cancelled = true;
      stopPolling();
    };
  }, [pollIntervalMs]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (screen.kind === "submitting") {
    return (
      <div style={styles.container} data-testid="progress-submitting">
        <Spinner />
        <p style={styles.subtitle}>Enviando solicitud de procesamiento…</p>
      </div>
    );
  }

  if (screen.kind === "failed") {
    return (
      <div style={styles.container} data-testid="progress-failed">
        <div style={styles.failIcon}>✕</div>
        <h2 style={styles.failTitle}>El procesamiento ha fallado</h2>
        <p style={styles.failReason}>{screen.reason}</p>
        <p style={styles.hint}>
          Run ID: <strong>#{runId}</strong>. Puedes relanzar el proceso desde el paso anterior.
        </p>
      </div>
    );
  }

  if (screen.kind === "completed") {
    return (
      <CompletedView
        runId={runId}
        metrics={screen.metrics}
        onViewDashboard={onViewDashboard}
      />
    );
  }

  // polling state
  return (
    <div style={styles.container} data-testid="progress-polling">
      <h2 style={styles.title}>Conciliando datos…</h2>
      <p style={styles.subtitle}>
        Run ID: <strong>#{runId}</strong>
      </p>

      <PhaseStepper currentPhase={screen.phase} />

      <Spinner />
      <p style={styles.pollingHint}>
        Actualizando cada {POLL_INTERVAL_MS / 1000} s…
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CompletedView
// ---------------------------------------------------------------------------

function CompletedView({
  runId,
  metrics,
  onViewDashboard,
}: {
  runId: number;
  metrics: SummaryMetrics;
  onViewDashboard?: () => void;
}): JSX.Element {
  return (
    <div style={styles.container} data-testid="progress-completed">
      <div style={styles.successIcon} aria-hidden>✓</div>
      <h2 style={styles.successTitle}>¡Conciliación completada!</h2>
      <p style={styles.subtitle}>
        Run ID: <strong>#{runId}</strong>
      </p>

      <div style={styles.metricsGrid}>
        <MetricCard
          label="SKUs analizados"
          value={metrics.total_skus}
          color="#1d4ed8"
          testId="metric-total-skus"
        />
        <MetricCard
          label="Enviados con error"
          value={metrics.sent_with_error}
          color="#dc2626"
          testId="metric-sent-with-error"
        />
        <MetricCard
          label="Enviados sin error"
          value={metrics.sent_ok}
          color="#16a34a"
          testId="metric-sent-ok"
        />
        <MetricCard
          label="No enviados"
          value={metrics.not_sent}
          color="#92400e"
          testId="metric-not-sent"
        />
        <MetricCard
          label="Solo en feed"
          value={metrics.desync_feed_only}
          color="#7c3aed"
          testId="metric-desync-feed"
        />
        <MetricCard
          label="Solo en Amazon"
          value={metrics.desync_amazon_only}
          color="#0891b2"
          testId="metric-desync-amazon"
        />
        <MetricCard
          label="Total errores"
          value={metrics.total_errors}
          color="#b91c1c"
          testId="metric-total-errors"
        />
      </div>

      <p style={styles.nextHint}>
        Los resultados completos están disponibles en el informe de la conciliación.
      </p>

      {onViewDashboard ? (
        <button
          type="button"
          style={styles.dashboardButton}
          onClick={onViewDashboard}
          data-testid="view-dashboard-button"
        >
          Ver informe
        </button>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// PhaseStepper
// ---------------------------------------------------------------------------

function PhaseStepper({ currentPhase }: { currentPhase: string | null }): JSX.Element {
  const currentIdx = currentPhase
    ? PIPELINE_PHASES.findIndex((p) => p === currentPhase)
    : -1;

  return (
    <div style={styles.stepper} data-testid="phase-stepper" aria-label="Fases del pipeline">
      {PIPELINE_PHASES.map((phase, idx) => {
        const isDone = currentIdx > idx;
        const isActive = currentIdx === idx;
        return (
          <div
            key={phase}
            style={{
              ...styles.stepperItem,
              ...(isDone ? styles.stepperDone : {}),
              ...(isActive ? styles.stepperActive : {}),
            }}
            aria-current={isActive ? "step" : undefined}
            data-testid={`phase-${phase.toLowerCase()}`}
          >
            <span style={styles.stepperDot}>
              {isDone ? "✓" : isActive ? "●" : "○"}
            </span>
            <span style={styles.stepperLabel}>{phase}</span>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// MetricCard
// ---------------------------------------------------------------------------

function MetricCard({
  label,
  value,
  color,
  testId,
}: {
  label: string;
  value: number;
  color: string;
  testId: string;
}): JSX.Element {
  return (
    <div style={{ ...styles.metricCard, borderTopColor: color }} data-testid={testId}>
      <span style={{ ...styles.metricValue, color }}>{value.toLocaleString()}</span>
      <span style={styles.metricLabel}>{label}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Spinner
// ---------------------------------------------------------------------------

function Spinner(): JSX.Element {
  return (
    <div
      style={styles.spinner}
      role="status"
      aria-label="Procesando"
      data-testid="spinner"
    />
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = {
  container: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    gap: "24px",
    padding: "32px 16px",
    textAlign: "center" as const,
  },
  title: {
    fontSize: "20px",
    fontWeight: 700,
    color: "var(--color-text)",
  },
  subtitle: {
    fontSize: "var(--font-size-sm)",
    color: "var(--color-text-muted)",
  },
  pollingHint: {
    fontSize: "var(--font-size-xs)",
    color: "var(--color-text-disabled)",
  },
  hint: {
    fontSize: "var(--font-size-xs)",
    color: "var(--color-text-muted)",
  },
  nextHint: {
    fontSize: "var(--font-size-sm)",
    color: "var(--color-text-muted)",
    maxWidth: "480px",
  },
  dashboardButton: {
    marginTop: "16px",
    padding: "10px 20px",
    fontSize: "14px",
    fontWeight: 600,
    borderRadius: "var(--radius-md)",
    border: "none",
    backgroundColor: "var(--color-primary)",
    color: "#fff",
    cursor: "pointer",
  },
  // Success
  successIcon: {
    width: "64px",
    height: "64px",
    borderRadius: "50%",
    backgroundColor: "#dcfce7",
    border: "2px solid #86efac",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "28px",
    color: "#16a34a",
    fontWeight: 700,
  },
  successTitle: {
    fontSize: "22px",
    fontWeight: 700,
    color: "#15803d",
  },
  // Failure
  failIcon: {
    width: "64px",
    height: "64px",
    borderRadius: "50%",
    backgroundColor: "#fee2e2",
    border: "2px solid #fca5a5",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "28px",
    color: "#dc2626",
    fontWeight: 700,
  },
  failTitle: {
    fontSize: "20px",
    fontWeight: 700,
    color: "#dc2626",
  },
  failReason: {
    fontSize: "var(--font-size-sm)",
    color: "#991b1b",
    backgroundColor: "#fef2f2",
    border: "1px solid #fca5a5",
    borderRadius: "var(--radius-md)",
    padding: "12px 16px",
    maxWidth: "480px",
    wordBreak: "break-word" as const,
  },
  // Phase stepper
  stepper: {
    display: "flex",
    gap: "8px",
    flexWrap: "wrap" as const,
    justifyContent: "center",
    width: "100%",
    maxWidth: "480px",
  },
  stepperItem: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    padding: "6px 14px",
    borderRadius: "var(--radius-sm)",
    backgroundColor: "var(--color-surface)",
    border: "1px solid var(--color-border)",
    fontSize: "var(--font-size-xs)",
    color: "var(--color-text-disabled)",
    transition: "all 0.2s",
  },
  stepperDone: {
    backgroundColor: "#f0fdf4",
    borderColor: "#86efac",
    color: "#15803d",
  },
  stepperActive: {
    backgroundColor: "#eff6ff",
    borderColor: "#93c5fd",
    color: "#1d4ed8",
    fontWeight: 600 as const,
  },
  stepperDot: {
    fontSize: "10px",
    lineHeight: 1,
  },
  stepperLabel: {
    fontSize: "13px",
  },
  // Metrics grid
  metricsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
    gap: "12px",
    width: "100%",
    maxWidth: "600px",
  },
  metricCard: {
    backgroundColor: "var(--color-surface)",
    border: "1px solid var(--color-border)",
    borderTop: "3px solid",
    borderRadius: "var(--radius-md)",
    padding: "16px 12px",
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    gap: "4px",
  },
  metricValue: {
    fontSize: "24px",
    fontWeight: 700,
    fontVariantNumeric: "tabular-nums",
  },
  metricLabel: {
    fontSize: "var(--font-size-xs)",
    color: "var(--color-text-muted)",
    textAlign: "center" as const,
    lineHeight: 1.3,
  },
  // Spinner
  spinner: {
    width: "40px",
    height: "40px",
    border: "3px solid var(--color-border)",
    borderTopColor: "#1d4ed8",
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
  },
} as const;
