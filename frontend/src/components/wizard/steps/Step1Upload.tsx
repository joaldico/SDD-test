import type { JSX } from "react";
import { FileDropZone } from "../FileDropZone";
import type { FileWizardState } from "../../../hooks/useWizardState";
import type { FileRole } from "../../../types/ingestion";
import { ROLE_LABELS } from "../../../types/ingestion";

interface Props {
  files: Record<FileRole, FileWizardState>;
  onFile: (role: FileRole, file: File) => void;
  onNext: () => void;
  allUploaded: boolean;
}

const ACCEPTED: Record<FileRole, string> = {
  occ_top: ".xlsx, .xlsm",
  wm_feed: ".csv, .txt, .tsv",
  amazon_report: ".xlsm, .xlsx",
};

const FILE_ROLES: FileRole[] = ["occ_top", "wm_feed", "amazon_report"];

export function Step1Upload({ files, onFile, onNext, allUploaded }: Props): JSX.Element {
  const anyUploading = FILE_ROLES.some((r) => files[r].uploadStatus === "uploading");

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h2 style={styles.title}>Carga de ficheros</h2>
        <p style={styles.subtitle}>
          Sube los tres ficheros de conciliación. Puedes arrastrarlos o hacer clic
          en cada zona.
        </p>
      </header>

      <div style={styles.grid} data-testid="upload-grid">
        {FILE_ROLES.map((role) => (
          <FileDropZone
            key={role}
            label={ROLE_LABELS[role]}
            acceptedExtensions={ACCEPTED[role]}
            file={files[role].file}
            uploadStatus={files[role].uploadStatus}
            uploadError={files[role].uploadError}
            onFile={(f) => onFile(role, f)}
            disabled={anyUploading && files[role].uploadStatus !== "uploading"}
            testId={`drop-zone-${role}`}
          />
        ))}
      </div>

      {/* Progress indicator */}
      <div style={styles.progress} aria-live="polite">
        {FILE_ROLES.map((role) => {
          const st = files[role].uploadStatus;
          const icon = st === "uploaded" ? "✓" : st === "uploading" ? "⟳" : st === "error" ? "✗" : "○";
          const color = st === "uploaded" ? "#16a34a" : st === "error" ? "#dc2626" : "var(--color-text-muted)";
          return (
            <span key={role} style={{ ...styles.progressItem, color }}>
              {icon} {ROLE_LABELS[role].split(" ")[0]}
            </span>
          );
        })}
      </div>

      <div style={styles.footer}>
        <button
          style={{
            ...styles.btn,
            ...(allUploaded ? styles.btnPrimary : styles.btnDisabled),
          }}
          disabled={!allUploaded}
          onClick={onNext}
          data-testid="step1-next"
          aria-label={
            allUploaded
              ? "Continuar al paso 2"
              : "Sube los tres ficheros para continuar"
          }
          title={!allUploaded ? "Sube los tres ficheros para continuar" : undefined}
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
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
    gap: "16px",
  },
  progress: {
    display: "flex",
    gap: "20px",
    fontSize: "var(--font-size-xs)",
    flexWrap: "wrap" as const,
  },
  progressItem: {
    display: "flex",
    alignItems: "center",
    gap: "4px",
  },
  footer: {
    display: "flex",
    justifyContent: "flex-end",
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
  btnPrimary: {
    backgroundColor: "var(--color-primary)",
    color: "#fff",
  },
  btnDisabled: {
    backgroundColor: "var(--color-border)",
    color: "var(--color-text-disabled)",
    cursor: "not-allowed",
  },
} as const;
