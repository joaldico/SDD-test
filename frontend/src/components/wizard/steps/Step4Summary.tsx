import type { JSX } from "react";
import type { FileWizardState } from "../../../hooks/useWizardState";
import type { FileRole } from "../../../types/ingestion";
import { FIELD_LABELS, REQUIRED_FIELDS, ROLE_LABELS } from "../../../types/ingestion";

interface Props {
  runId: number | null;
  files: Record<FileRole, FileWizardState>;
  allConfirmed: boolean;
  onProcess: () => void;
  onBack: () => void;
  processing?: boolean;
}

const FILE_ROLES: FileRole[] = ["occ_top", "wm_feed", "amazon_report"];

export function Step4Summary({
  runId,
  files,
  allConfirmed,
  onProcess,
  onBack,
  processing = false,
}: Props): JSX.Element {
  /**
   * RNF-08: The "Procesar" button is LOCKED until every mandatory file has a
   * confirmed mapping. This is the single enforced gate in the frontend.
   */
  const canProcess = allConfirmed && !processing;

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h2 style={styles.title}>Resumen</h2>
        <p style={styles.subtitle}>
          Revisa la configuración antes de iniciar la conciliación.
          Run ID: <strong>#{runId}</strong>
        </p>
      </header>

      {/* File cards */}
      <div style={styles.cards}>
        {FILE_ROLES.map((role) => (
          <FileCard key={role} role={role} fileState={files[role]} />
        ))}
      </div>

      {/* RNF-08 gate banner */}
      {!allConfirmed && (
        <div style={styles.gateBanner} role="alert" data-testid="gate-banner">
          <span style={styles.gateIcon}>🔒</span>
          <div>
            <p style={styles.gateTitle}>
              Botón bloqueado — mapeo incompleto (RNF-08)
            </p>
            <p style={styles.gateDetail}>
              Confirma el mapeo de los siguientes ficheros:{" "}
              {FILE_ROLES.filter((r) => !files[r].mappingConfirmed)
                .map((r) => ROLE_LABELS[r].split(" ")[0])
                .join(", ")}
            </p>
          </div>
        </div>
      )}

      {/* Process button */}
      <div style={styles.footer}>
        <button style={{ ...styles.btn, ...styles.btnSecondary }} onClick={onBack}>
          ← Atrás
        </button>

        <button
          style={{
            ...styles.btn,
            ...(canProcess ? styles.btnProcess : styles.btnProcessDisabled),
          }}
          disabled={!canProcess}
          onClick={onProcess}
          data-testid="process-button"
          aria-disabled={!canProcess}
          title={
            !allConfirmed
              ? "Confirma el mapeo de todos los ficheros para procesar (RNF-08)"
              : processing
                ? "Procesando…"
                : undefined
          }
        >
          {processing ? "Procesando…" : "🚀 Procesar conciliación"}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// FileCard — summary card for a single file
// ---------------------------------------------------------------------------

interface FileCardProps {
  role: FileRole;
  fileState: FileWizardState;
}

function FileCard({ role, fileState }: FileCardProps): JSX.Element {
  const { file, uploadStatus, sourceFileId, selectedSheet, mappingConfirmed, pendingMappings, mappingWarnings } =
    fileState;
  const requiredFields = REQUIRED_FIELDS[role];

  const statusColor = mappingConfirmed ? "#16a34a" : "#dc2626";
  const statusLabel = mappingConfirmed ? "Mapeo confirmado ✓" : "Mapeo pendiente ✗";

  return (
    <div
      style={{
        ...styles.card,
        ...(mappingConfirmed ? styles.cardConfirmed : styles.cardPending),
      }}
      data-testid={`summary-card-${role}`}
    >
      {/* Card header */}
      <div style={styles.cardHeader}>
        <h3 style={styles.cardTitle}>{ROLE_LABELS[role]}</h3>
        <span style={{ ...styles.statusBadge, backgroundColor: mappingConfirmed ? "#dcfce7" : "#fee2e2", color: statusColor }}>
          {statusLabel}
        </span>
      </div>

      {/* File details */}
      <div style={styles.cardBody}>
        <Row label="Fichero" value={file?.name ?? "—"} />
        <Row label="ID" value={sourceFileId ? `#${sourceFileId}` : "—"} />
        {selectedSheet && <Row label="Hoja" value={selectedSheet} />}
        {uploadStatus === "uploaded" && (
          <Row
            label="Estado de carga"
            value="Subido correctamente"
            valueColor="#16a34a"
          />
        )}

        {/* Mapped fields */}
        {mappingConfirmed && (
          <div style={styles.fieldList}>
            {requiredFields.map((field) => {
              const colIdx = pendingMappings[field];
              return (
                <div key={field} style={styles.fieldRow}>
                  <span style={styles.fieldName}>{FIELD_LABELS[field] ?? field}</span>
                  <span style={styles.fieldValue}>
                    {colIdx !== undefined ? `Columna ${colIdx}` : "—"}
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {/* Mapping warnings */}
        {mappingWarnings.length > 0 && (
          <p style={styles.warningNote}>
            ⚠ {mappingWarnings.length} advertencia(s) — modo degradado
          </p>
        )}
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  valueColor,
}: {
  label: string;
  value: string;
  valueColor?: string;
}): JSX.Element {
  return (
    <div style={styles.row}>
      <span style={styles.rowLabel}>{label}:</span>
      <span style={{ ...styles.rowValue, ...(valueColor ? { color: valueColor } : {}) }}>
        {value}
      </span>
    </div>
  );
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "24px",
  },
  header: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "6px",
  },
  title: {
    fontSize: "20px",
    fontWeight: 700,
    color: "var(--color-text)",
  },
  subtitle: {
    fontSize: "var(--font-size-sm)",
    color: "var(--color-text-muted)",
    lineHeight: 1.6,
  },
  cards: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
    gap: "16px",
  },
  card: {
    backgroundColor: "var(--color-surface)",
    border: "1px solid var(--color-border)",
    borderRadius: "var(--radius-md)",
    padding: "16px",
    display: "flex",
    flexDirection: "column" as const,
    gap: "12px",
  },
  cardConfirmed: {
    borderColor: "#86efac",
    backgroundColor: "#f0fdf4",
  },
  cardPending: {
    borderColor: "#fca5a5",
    backgroundColor: "#fef2f2",
  },
  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: "8px",
  },
  cardTitle: {
    fontSize: "var(--font-size-sm)",
    fontWeight: 700,
    color: "var(--color-text)",
    flex: 1,
  },
  statusBadge: {
    fontSize: "var(--font-size-xs)",
    padding: "2px 8px",
    borderRadius: "var(--radius-sm)",
    fontWeight: 600,
    whiteSpace: "nowrap" as const,
  },
  cardBody: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "6px",
  },
  row: {
    display: "flex",
    gap: "8px",
    alignItems: "baseline",
  },
  rowLabel: {
    fontSize: "var(--font-size-xs)",
    color: "var(--color-text-muted)",
    flexShrink: 0,
  },
  rowValue: {
    fontSize: "var(--font-size-xs)",
    color: "var(--color-text)",
    overflow: "hidden" as const,
    textOverflow: "ellipsis" as const,
    whiteSpace: "nowrap" as const,
  },
  fieldList: {
    marginTop: "4px",
    display: "flex",
    flexDirection: "column" as const,
    gap: "4px",
    borderTop: "1px solid var(--color-border)",
    paddingTop: "8px",
  },
  fieldRow: {
    display: "flex",
    justifyContent: "space-between",
    gap: "8px",
  },
  fieldName: {
    fontSize: "var(--font-size-xs)",
    color: "var(--color-text-muted)",
  },
  fieldValue: {
    fontSize: "var(--font-size-xs)",
    fontWeight: 600,
    color: "var(--color-text)",
    fontFamily: "monospace",
  },
  warningNote: {
    fontSize: "var(--font-size-xs)",
    color: "#92400e",
    backgroundColor: "#fef3c7",
    padding: "4px 8px",
    borderRadius: "var(--radius-sm)",
  },
  gateBanner: {
    display: "flex",
    alignItems: "flex-start",
    gap: "12px",
    padding: "16px",
    backgroundColor: "#fef2f2",
    border: "1px solid #fca5a5",
    borderRadius: "var(--radius-md)",
  },
  gateIcon: {
    fontSize: "20px",
    flexShrink: 0,
    lineHeight: 1.4,
  },
  gateTitle: {
    fontSize: "var(--font-size-sm)",
    fontWeight: 700,
    color: "#dc2626",
    marginBottom: "4px",
  },
  gateDetail: {
    fontSize: "var(--font-size-xs)",
    color: "#991b1b",
  },
  footer: {
    display: "flex",
    justifyContent: "space-between",
    paddingTop: "8px",
    borderTop: "1px solid var(--color-border)",
  },
  btn: {
    padding: "10px 28px",
    borderRadius: "var(--radius-md)",
    fontSize: "var(--font-size-sm)",
    fontWeight: 600,
    border: "none",
    cursor: "pointer",
    transition: "background 0.15s, opacity 0.15s",
  },
  btnSecondary: {
    backgroundColor: "transparent",
    color: "var(--color-text-muted)",
    border: "1px solid var(--color-border)",
  },
  btnProcess: {
    backgroundColor: "#16a34a",
    color: "#fff",
    fontSize: "15px",
    padding: "12px 32px",
  },
  btnProcessDisabled: {
    backgroundColor: "var(--color-border)",
    color: "var(--color-text-disabled)",
    cursor: "not-allowed",
    opacity: 0.7,
  },
} as const;
