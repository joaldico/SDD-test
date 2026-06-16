import { useRef, useState, type DragEvent, type ChangeEvent, type JSX } from "react";

interface Props {
  /** Role label shown in the drop zone */
  label: string;
  /** Accepted extensions shown as hint */
  acceptedExtensions: string;
  /** Currently selected file (or null) */
  file: File | null;
  /** Upload status for this role */
  uploadStatus: "idle" | "uploading" | "uploaded" | "error";
  /** Upload error message (shown when status === "error") */
  uploadError: string | null;
  /** Called when user selects or drops a file */
  onFile: (file: File) => void;
  /** Disable the zone (e.g. while another upload is in progress) */
  disabled?: boolean;
  /** Explicit test id (defaults to slugified label) */
  testId?: string;
}

export function FileDropZone({
  label,
  acceptedExtensions,
  file,
  uploadStatus,
  uploadError,
  onFile,
  disabled = false,
  testId,
}: Props): JSX.Element {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (!disabled) setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (disabled) return;
    const dropped = e.dataTransfer.files[0];
    if (dropped) onFile(dropped);
  };

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const chosen = e.target.files?.[0];
    if (chosen) onFile(chosen);
    // Reset so the same file can be re-selected after an error
    e.target.value = "";
  };

  const handleClick = () => {
    if (!disabled) inputRef.current?.click();
  };

  const isUploaded = uploadStatus === "uploaded";
  const isUploading = uploadStatus === "uploading";
  const isError = uploadStatus === "error";

  const zoneStyle: React.CSSProperties = {
    ...styles.zone,
    ...(isDragging ? styles.zoneDragging : {}),
    ...(isUploaded ? styles.zoneUploaded : {}),
    ...(isError ? styles.zoneError : {}),
    ...(disabled && !isUploaded ? styles.zoneDisabled : {}),
    cursor: disabled ? "not-allowed" : "pointer",
  };

  return (
    <div style={styles.wrapper}>
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label={`Zona de carga: ${label}`}
        style={zoneStyle}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") handleClick();
        }}
        data-testid={testId ?? `drop-zone-${label.replace(/\s+/g, "-").toLowerCase()}`}
      >
        <input
          ref={inputRef}
          type="file"
          style={styles.hiddenInput}
          tabIndex={-1}
          aria-hidden="true"
          onChange={handleChange}
        />

        {/* Status icon */}
        <span style={styles.icon} aria-hidden="true">
          {isUploaded ? "✓" : isUploading ? "⟳" : isError ? "⚠" : "⬆"}
        </span>

        {/* Role label */}
        <span style={styles.roleLabel}>{label}</span>

        {/* File info or prompt */}
        {file ? (
          <span style={styles.fileName} title={file.name}>
            {file.name.length > 40 ? `…${file.name.slice(-37)}` : file.name}
          </span>
        ) : (
          <span style={styles.prompt}>
            Arrastra aquí o haz clic para seleccionar
            <br />
            <span style={styles.hint}>{acceptedExtensions}</span>
          </span>
        )}

        {/* Upload state label */}
        {isUploading && <span style={styles.statusLabel}>Subiendo…</span>}
        {isUploaded && <span style={{ ...styles.statusLabel, ...styles.statusOk }}>Subido correctamente</span>}
      </div>

      {/* Error message */}
      {isError && uploadError && (
        <p role="alert" style={styles.errorMsg}>
          {uploadError}
        </p>
      )}
    </div>
  );
}

const styles = {
  wrapper: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "6px",
  },
  zone: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    justifyContent: "center",
    gap: "8px",
    padding: "28px 20px",
    border: "2px dashed var(--color-border)",
    borderRadius: "var(--radius-md)",
    backgroundColor: "var(--color-surface)",
    textAlign: "center" as const,
    userSelect: "none" as const,
    transition: "border-color 0.15s, background 0.15s",
    minHeight: "140px",
  },
  zoneDragging: {
    borderColor: "var(--color-primary)",
    backgroundColor: "var(--color-primary-light)",
  },
  zoneUploaded: {
    borderColor: "#22c55e",
    backgroundColor: "#f0fdf4",
    borderStyle: "solid",
  },
  zoneError: {
    borderColor: "#ef4444",
    backgroundColor: "#fef2f2",
  },
  zoneDisabled: {
    opacity: 0.6,
  },
  hiddenInput: {
    display: "none",
  },
  icon: {
    fontSize: "24px",
    lineHeight: 1,
  },
  roleLabel: {
    fontSize: "var(--font-size-sm)",
    fontWeight: 600,
    color: "var(--color-text)",
  },
  fileName: {
    fontSize: "var(--font-size-xs)",
    color: "var(--color-text-muted)",
    wordBreak: "break-all" as const,
    maxWidth: "220px",
  },
  prompt: {
    fontSize: "var(--font-size-xs)",
    color: "var(--color-text-muted)",
    lineHeight: 1.6,
  },
  hint: {
    opacity: 0.7,
  },
  statusLabel: {
    fontSize: "var(--font-size-xs)",
    color: "var(--color-text-muted)",
    fontStyle: "italic",
  },
  statusOk: {
    color: "#16a34a",
    fontStyle: "normal",
    fontWeight: 600,
  },
  errorMsg: {
    fontSize: "var(--font-size-xs)",
    color: "#dc2626",
    padding: "4px 8px",
    backgroundColor: "#fef2f2",
    borderRadius: "var(--radius-sm)",
    border: "1px solid #fecaca",
  },
} as const;
