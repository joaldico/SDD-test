import { useEffect, useState, type JSX } from "react";
import { PreviewTable } from "../PreviewTable";
import type { FileWizardState } from "../../../hooks/useWizardState";
import type { FileRole } from "../../../types/ingestion";
import {
  FIELD_LABELS,
  REQUIRED_FIELDS,
  ROLE_LABELS,
} from "../../../types/ingestion";

interface Props {
  files: Record<FileRole, FileWizardState>;
  onFetchPreview: (role: FileRole, sheet?: string) => void;
  onMappingChange: (role: FileRole, logicalField: string, columnIndex: number) => void;
  onConfirmMapping: (role: FileRole) => void;
  onNext: () => void;
  onBack: () => void;
  allConfirmed: boolean;
}

const FILE_ROLES: FileRole[] = ["occ_top", "wm_feed", "amazon_report"];

export function Step3Mapping({
  files,
  onFetchPreview,
  onMappingChange,
  onConfirmMapping,
  onNext,
  onBack,
  allConfirmed,
}: Props): JSX.Element {
  const [activeRole, setActiveRole] = useState<FileRole>("occ_top");

  // Fetch preview for active role when entering the step
  useEffect(() => {
    const f = files[activeRole];
    if (f.previewStatus === "idle" && f.sourceFileId !== null) {
      onFetchPreview(activeRole, f.selectedSheet ?? undefined);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeRole]);

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h2 style={styles.title}>Mapeo de columnas</h2>
        <p style={styles.subtitle}>
          Confirma qué columna corresponde a cada campo lógico en cada fichero.
          Las sugerencias del asistente (★) están pre-seleccionadas.
        </p>
      </header>

      {/* File tabs */}
      <div style={styles.tabs} role="tablist" aria-label="Ficheros">
        {FILE_ROLES.map((role) => {
          const confirmed = files[role].mappingConfirmed;
          return (
            <button
              key={role}
              role="tab"
              aria-selected={activeRole === role}
              aria-controls={`tabpanel-${role}`}
              id={`tab-${role}`}
              style={{
                ...styles.tab,
                ...(activeRole === role ? styles.tabActive : {}),
              }}
              onClick={() => setActiveRole(role)}
              data-testid={`tab-${role}`}
            >
              {confirmed && <span style={styles.checkMark} aria-label="Confirmado">✓</span>}
              <span>{ROLE_LABELS[role].split(" ")[0]}</span>
            </button>
          );
        })}
      </div>

      {/* Tab panel */}
      <div
        role="tabpanel"
        id={`tabpanel-${activeRole}`}
        aria-labelledby={`tab-${activeRole}`}
        key={activeRole}
        style={styles.panel}
      >
        <FilePanel
          role={activeRole}
          fileState={files[activeRole]}
          onFetchPreview={onFetchPreview}
          onMappingChange={onMappingChange}
          onConfirmMapping={onConfirmMapping}
        />
      </div>

      <div style={styles.footer}>
        <button style={{ ...styles.btn, ...styles.btnSecondary }} onClick={onBack}>
          ← Atrás
        </button>
        <button
          style={{
            ...styles.btn,
            ...(allConfirmed ? styles.btnPrimary : styles.btnDisabled),
          }}
          disabled={!allConfirmed}
          onClick={onNext}
          data-testid="step3-next"
          title={
            !allConfirmed
              ? "Confirma el mapeo de los tres ficheros para continuar"
              : undefined
          }
        >
          Ver resumen →
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// FilePanel — per-file mapping UI inside the tab panel
// ---------------------------------------------------------------------------

interface FilePanelProps {
  role: FileRole;
  fileState: FileWizardState;
  onFetchPreview: (role: FileRole, sheet?: string) => void;
  onMappingChange: (role: FileRole, logicalField: string, columnIndex: number) => void;
  onConfirmMapping: (role: FileRole) => void;
}

function FilePanel({
  role,
  fileState,
  onFetchPreview,
  onMappingChange,
  onConfirmMapping,
}: FilePanelProps): JSX.Element {
  const { preview, previewStatus, previewError, pendingMappings, mappingConfirmed, mappingWarnings } =
    fileState;

  const requiredFields = REQUIRED_FIELDS[role];
  const allRequiredMapped = requiredFields.every(
    (f) => pendingMappings[f] !== undefined
  );

  // Compute set of suggested column indices for highlighting
  const suggestedIndices = new Set(
    Object.values(preview?.suggestions ?? {}).map((s) => s.column_index)
  );

  if (previewStatus === "idle") {
    return (
      <div style={panelStyles.placeholder}>
        <button
          style={panelStyles.fetchBtn}
          onClick={() => onFetchPreview(role, fileState.selectedSheet ?? undefined)}
        >
          Cargar previsualización
        </button>
      </div>
    );
  }

  if (previewStatus === "loading") {
    return (
      <p style={panelStyles.loading} aria-live="polite">
        Cargando previsualización…
      </p>
    );
  }

  if (previewStatus === "error") {
    return (
      <div style={panelStyles.errorBox} role="alert">
        <p style={panelStyles.errorText}>⚠ {previewError}</p>
        <button
          style={panelStyles.retryBtn}
          onClick={() => onFetchPreview(role, fileState.selectedSheet ?? undefined)}
        >
          Reintentar
        </button>
      </div>
    );
  }

  if (!preview) return <></>;

  return (
    <div style={panelStyles.container}>
      {/* Preview table */}
      <PreviewTable
        preview={preview}
        suggestedIndices={suggestedIndices}
        mappedIndex={
          pendingMappings["sku"] !== undefined ? pendingMappings["sku"] : null
        }
      />

      {/* Mapping selectors */}
      <div style={panelStyles.mappingSection}>
        <h4 style={panelStyles.mappingTitle}>Asignación de campos</h4>
        <div style={panelStyles.fieldGrid}>
          {requiredFields.map((field) => {
            const suggestion = preview.suggestions[field];
            const currentIdx = pendingMappings[field];
            return (
              <FieldSelector
                key={field}
                field={field}
                headers={preview.headers}
                selectedIndex={currentIdx}
                suggestion={suggestion}
                onChange={(idx) => onMappingChange(role, field, idx)}
              />
            );
          })}
        </div>
      </div>

      {/* Mapping warnings */}
      {mappingWarnings.length > 0 && (
        <div style={panelStyles.warningsBox} role="alert">
          <p style={panelStyles.warningTitle}>⚠ Advertencias del mapeo:</p>
          {mappingWarnings.map((w, i) => (
            <p key={i} style={panelStyles.warningItem}>
              {w.message}
              {w.sample && (
                <span style={panelStyles.warningCode}>
                  {" "}
                  (muestra: {w.sample.join(", ")})
                </span>
              )}
            </p>
          ))}
        </div>
      )}

      {/* Confirm button */}
      {mappingConfirmed ? (
        <div style={panelStyles.confirmed} data-testid={`mapping-confirmed-${role}`}>
          <span style={panelStyles.confirmedIcon}>✓</span>
          <span>Mapeo confirmado</span>
          <button
            style={panelStyles.reconfirmBtn}
            onClick={() => onConfirmMapping(role)}
          >
            Reconfirmar
          </button>
        </div>
      ) : (
        <button
          style={{
            ...panelStyles.confirmBtn,
            ...(!allRequiredMapped ? panelStyles.confirmBtnDisabled : {}),
          }}
          disabled={!allRequiredMapped}
          onClick={() => onConfirmMapping(role)}
          data-testid={`confirm-mapping-${role}`}
          title={
            !allRequiredMapped
              ? `Selecciona todos los campos requeridos: ${requiredFields
                  .filter((f) => pendingMappings[f] === undefined)
                  .map((f) => FIELD_LABELS[f] ?? f)
                  .join(", ")}`
              : undefined
          }
        >
          Confirmar mapeo de {ROLE_LABELS[role].split(" ")[0]}
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// FieldSelector — dropdown for a single logical field
// ---------------------------------------------------------------------------

interface FieldSelectorProps {
  field: string;
  headers: { index: number; name: string }[];
  selectedIndex: number | undefined;
  suggestion: { column_index: number; confidence: number; reason: string } | undefined;
  onChange: (columnIndex: number) => void;
}

function FieldSelector({
  field,
  headers,
  selectedIndex,
  suggestion,
  onChange,
}: FieldSelectorProps): JSX.Element {
  const label = FIELD_LABELS[field] ?? field;
  const confidencePct = suggestion
    ? `${Math.round(suggestion.confidence * 100)}%`
    : null;

  return (
    <div style={fieldStyles.wrapper}>
      <label htmlFor={`field-${field}`} style={fieldStyles.label}>
        {label}
        <span style={fieldStyles.required} title="Campo obligatorio">
          *
        </span>
      </label>

      <select
        id={`field-${field}`}
        value={selectedIndex !== undefined ? String(selectedIndex) : ""}
        onChange={(e) => onChange(Number(e.target.value))}
        style={fieldStyles.select}
        data-testid={`field-select-${field}`}
      >
        <option value="" disabled>
          — Selecciona columna —
        </option>
        {headers.map((h) => {
          const isSuggested = suggestion?.column_index === h.index;
          return (
            <option key={h.index} value={String(h.index)}>
              {h.index}: {h.name || "(sin nombre)"}
              {isSuggested ? ` ★ (${confidencePct})` : ""}
            </option>
          );
        })}
      </select>

      {suggestion && selectedIndex === suggestion.column_index && (
        <p style={fieldStyles.suggestionNote} aria-live="polite">
          ★ Sugerencia ({confidencePct}): {suggestion.reason}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

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
  tabs: {
    display: "flex",
    gap: "4px",
    borderBottom: "2px solid var(--color-border)",
    paddingBottom: "0",
  },
  tab: {
    padding: "8px 20px",
    fontSize: "var(--font-size-sm)",
    fontWeight: 500,
    border: "none",
    borderBottom: "2px solid transparent",
    backgroundColor: "transparent",
    cursor: "pointer",
    color: "var(--color-text-muted)",
    display: "flex",
    alignItems: "center",
    gap: "6px",
    marginBottom: "-2px",
    transition: "color 0.15s, border-color 0.15s",
  },
  tabActive: {
    color: "var(--color-primary)",
    borderBottom: "2px solid var(--color-primary)",
    fontWeight: 600,
  },
  checkMark: {
    color: "#16a34a",
    fontWeight: 700,
    fontSize: "14px",
  },
  panel: {
    backgroundColor: "var(--color-surface)",
    border: "1px solid var(--color-border)",
    borderRadius: "var(--radius-md)",
    padding: "20px",
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

const panelStyles = {
  container: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "20px",
  },
  placeholder: {
    display: "flex",
    justifyContent: "center",
    padding: "40px",
  },
  fetchBtn: {
    padding: "10px 24px",
    borderRadius: "var(--radius-md)",
    backgroundColor: "var(--color-primary)",
    color: "#fff",
    border: "none",
    fontWeight: 600,
    cursor: "pointer",
    fontSize: "var(--font-size-sm)",
  },
  loading: {
    fontSize: "var(--font-size-sm)",
    color: "var(--color-text-muted)",
    fontStyle: "italic",
    padding: "20px 0",
  },
  errorBox: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "10px",
    padding: "16px",
    backgroundColor: "#fef2f2",
    border: "1px solid #fecaca",
    borderRadius: "var(--radius-md)",
  },
  errorText: {
    fontSize: "var(--font-size-sm)",
    color: "#dc2626",
  },
  retryBtn: {
    alignSelf: "flex-start",
    padding: "6px 16px",
    borderRadius: "var(--radius-sm)",
    backgroundColor: "#dc2626",
    color: "#fff",
    border: "none",
    cursor: "pointer",
    fontSize: "var(--font-size-xs)",
  },
  mappingSection: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "12px",
  },
  mappingTitle: {
    fontSize: "var(--font-size-sm)",
    fontWeight: 700,
    color: "var(--color-text)",
  },
  fieldGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
    gap: "16px",
  },
  warningsBox: {
    padding: "12px 16px",
    backgroundColor: "#fef3c7",
    border: "1px solid #fde68a",
    borderRadius: "var(--radius-md)",
    display: "flex",
    flexDirection: "column" as const,
    gap: "6px",
  },
  warningTitle: {
    fontSize: "var(--font-size-sm)",
    fontWeight: 600,
    color: "#92400e",
  },
  warningItem: {
    fontSize: "var(--font-size-xs)",
    color: "#78350f",
  },
  warningCode: {
    fontFamily: "monospace",
    opacity: 0.8,
  },
  confirmed: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    padding: "12px 16px",
    backgroundColor: "#f0fdf4",
    border: "1px solid #86efac",
    borderRadius: "var(--radius-md)",
    fontSize: "var(--font-size-sm)",
    color: "#15803d",
    fontWeight: 600,
  },
  confirmedIcon: {
    fontSize: "18px",
    color: "#16a34a",
  },
  reconfirmBtn: {
    marginLeft: "auto",
    padding: "4px 14px",
    borderRadius: "var(--radius-sm)",
    border: "1px solid #86efac",
    backgroundColor: "transparent",
    color: "#15803d",
    cursor: "pointer",
    fontSize: "var(--font-size-xs)",
  },
  confirmBtn: {
    alignSelf: "flex-start",
    padding: "10px 24px",
    borderRadius: "var(--radius-md)",
    backgroundColor: "var(--color-primary)",
    color: "#fff",
    border: "none",
    fontWeight: 600,
    cursor: "pointer",
    fontSize: "var(--font-size-sm)",
    transition: "background 0.15s",
  },
  confirmBtnDisabled: {
    backgroundColor: "var(--color-border)",
    color: "var(--color-text-disabled)",
    cursor: "not-allowed",
  },
} as const;

const fieldStyles = {
  wrapper: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "6px",
  },
  label: {
    fontSize: "var(--font-size-sm)",
    fontWeight: 600,
    color: "var(--color-text)",
    display: "flex",
    gap: "4px",
    alignItems: "baseline",
  },
  required: {
    color: "#dc2626",
    fontSize: "14px",
  },
  select: {
    padding: "8px 10px",
    borderRadius: "var(--radius-sm)",
    border: "1px solid var(--color-border)",
    fontSize: "var(--font-size-sm)",
    color: "var(--color-text)",
    backgroundColor: "var(--color-surface)",
    cursor: "pointer",
    width: "100%",
  },
  suggestionNote: {
    fontSize: "var(--font-size-xs)",
    color: "var(--color-primary)",
    backgroundColor: "var(--color-primary-light)",
    padding: "4px 8px",
    borderRadius: "var(--radius-sm)",
    lineHeight: 1.5,
  },
} as const;
