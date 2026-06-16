import { useEffect, type JSX } from "react";
import type { FileWizardState } from "../../../hooks/useWizardState";
import type { FileRole } from "../../../types/ingestion";
import { ROLE_LABELS } from "../../../types/ingestion";

interface Props {
  files: Record<FileRole, FileWizardState>;
  excelRoles: FileRole[];
  onSheetChange: (role: FileRole, sheet: string) => void;
  onNext: () => void;
  onBack: () => void;
  /** Called when the component needs to fetch the preview for a role */
  onFetchPreview: (role: FileRole, sheet?: string) => void;
}

export function Step2SheetPicker({
  files,
  excelRoles,
  onSheetChange,
  onNext,
  onBack,
  onFetchPreview,
}: Props): JSX.Element {
  // Trigger preview fetch for each excel role on mount (to get available_sheets)
  useEffect(() => {
    for (const role of excelRoles) {
      const f = files[role];
      if (f.previewStatus === "idle" && f.sourceFileId !== null) {
        onFetchPreview(role, f.selectedSheet ?? undefined);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (excelRoles.length === 0) {
    // No Excel files — auto-advance
    return (
      <div style={styles.container}>
        <p style={styles.skipNote}>
          Ningún fichero requiere selección de hoja (todos son CSV/TXT).
        </p>
        <div style={styles.footer}>
          <button style={{ ...styles.btn, ...styles.btnSecondary }} onClick={onBack}>
            ← Atrás
          </button>
          <button
            style={{ ...styles.btn, ...styles.btnPrimary }}
            onClick={onNext}
            data-testid="step2-next"
          >
            Siguiente →
          </button>
        </div>
      </div>
    );
  }

  const allReady = excelRoles.every(
    (r) => files[r].previewStatus === "loaded" || files[r].previewStatus === "error"
  );

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h2 style={styles.title}>Selección de hoja</h2>
        <p style={styles.subtitle}>
          Elige la hoja de trabajo para cada fichero Excel. Las hojas disponibles
          se detectan automáticamente.
        </p>
      </header>

      <div style={styles.cards}>
        {excelRoles.map((role) => {
          const f = files[role];
          const sheets = f.preview?.available_sheets ?? [];
          const selected = f.selectedSheet ?? f.preview?.sheet ?? "";

          return (
            <div key={role} style={styles.card}>
              <h3 style={styles.cardTitle}>{ROLE_LABELS[role]}</h3>
              <p style={styles.fileName} title={f.file?.name}>
                {f.file?.name}
              </p>

              {f.previewStatus === "loading" && (
                <p style={styles.loading} aria-live="polite">
                  Analizando hojas…
                </p>
              )}

              {f.previewStatus === "error" && (
                <p style={styles.error} role="alert">
                  ⚠ {f.previewError}
                </p>
              )}

              {f.previewStatus === "loaded" && sheets.length > 0 && (
                <div style={styles.sheetGroup}>
                  <label htmlFor={`sheet-${role}`} style={styles.label}>
                    Hoja activa:
                  </label>
                  <select
                    id={`sheet-${role}`}
                    value={selected}
                    onChange={(e) => onSheetChange(role, e.target.value)}
                    style={styles.select}
                    data-testid={`sheet-select-${role}`}
                  >
                    {sheets.map((s) => (
                      <option key={s.name} value={s.name}>
                        {s.name} ({s.rows.toLocaleString()} filas)
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {f.previewStatus === "loaded" && sheets.length === 0 && (
                <p style={styles.noSheets}>
                  No se detectaron hojas múltiples.
                </p>
              )}
            </div>
          );
        })}
      </div>

      <div style={styles.footer}>
        <button style={{ ...styles.btn, ...styles.btnSecondary }} onClick={onBack}>
          ← Atrás
        </button>
        <button
          style={{
            ...styles.btn,
            ...(allReady ? styles.btnPrimary : styles.btnDisabled),
          }}
          disabled={!allReady}
          onClick={onNext}
          data-testid="step2-next"
          title={!allReady ? "Esperando análisis de hojas…" : undefined}
        >
          Siguiente →
        </button>
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "24px",
  },
  skipNote: {
    fontSize: "var(--font-size-sm)",
    color: "var(--color-text-muted)",
    padding: "16px",
    backgroundColor: "var(--color-surface)",
    borderRadius: "var(--radius-md)",
    border: "1px solid var(--color-border)",
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
    display: "flex",
    flexDirection: "column" as const,
    gap: "16px",
  },
  card: {
    backgroundColor: "var(--color-surface)",
    border: "1px solid var(--color-border)",
    borderRadius: "var(--radius-md)",
    padding: "20px",
    display: "flex",
    flexDirection: "column" as const,
    gap: "10px",
  },
  cardTitle: {
    fontSize: "var(--font-size-sm)",
    fontWeight: 700,
    color: "var(--color-text)",
  },
  fileName: {
    fontSize: "var(--font-size-xs)",
    color: "var(--color-text-muted)",
    overflow: "hidden" as const,
    textOverflow: "ellipsis" as const,
    whiteSpace: "nowrap" as const,
  },
  loading: {
    fontSize: "var(--font-size-sm)",
    color: "var(--color-text-muted)",
    fontStyle: "italic",
  },
  error: {
    fontSize: "var(--font-size-sm)",
    color: "#dc2626",
  },
  sheetGroup: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
  },
  label: {
    fontSize: "var(--font-size-sm)",
    color: "var(--color-text)",
    fontWeight: 500,
    flexShrink: 0,
  },
  select: {
    flex: 1,
    padding: "8px 10px",
    borderRadius: "var(--radius-sm)",
    border: "1px solid var(--color-border)",
    fontSize: "var(--font-size-sm)",
    color: "var(--color-text)",
    backgroundColor: "var(--color-surface)",
    cursor: "pointer",
  },
  noSheets: {
    fontSize: "var(--font-size-xs)",
    color: "var(--color-text-muted)",
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
    transition: "background 0.15s",
  },
  btnPrimary: {
    backgroundColor: "var(--color-primary)",
    color: "#fff",
  },
  btnSecondary: {
    backgroundColor: "transparent",
    color: "var(--color-text-muted)",
    border: "1px solid var(--color-border)",
  },
  btnDisabled: {
    backgroundColor: "var(--color-border)",
    color: "var(--color-text-disabled)",
    cursor: "not-allowed",
  },
} as const;
