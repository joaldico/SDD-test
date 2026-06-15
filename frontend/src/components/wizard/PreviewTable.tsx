import type { JSX } from "react";
import type { HeaderInfo, PreviewResponse } from "../../types/ingestion";

interface Props {
  preview: PreviewResponse;
  /** Set of suggested column indices — highlighted in the header */
  suggestedIndices: Set<number>;
  /** The currently mapped column index per field (highlighted with a marker) */
  mappedIndex: number | null;
}

export function PreviewTable({ preview, suggestedIndices, mappedIndex }: Props): JSX.Element {
  const { headers, sample_rows, warnings, block, discarded_rows } = preview;

  return (
    <div style={styles.container}>
      {/* Block info */}
      {block && (
        <p style={styles.blockNote}>
          Bloque detectado: &ldquo;{block.title_matched}&rdquo; — datos desde fila{" "}
          {block.data_start_row}
        </p>
      )}

      {/* Discarded rows info */}
      {discarded_rows > 0 && (
        <p style={styles.discardNote}>
          ⚠ {discarded_rows} fila(s) de ejemplo descartada(s) (EB-04)
        </p>
      )}

      {/* Warnings */}
      {warnings.map((w, i) => (
        <p key={i} style={styles.warnNote}>
          ⚠ {w.message}
        </p>
      ))}

      {/* Table */}
      <div style={styles.tableWrapper}>
        <table style={styles.table} role="grid" aria-label="Vista previa del fichero">
          <thead>
            <tr>
              {headers.map((h: HeaderInfo) => (
                <th
                  key={h.index}
                  style={{
                    ...styles.th,
                    ...(suggestedIndices.has(h.index) ? styles.thSuggested : {}),
                    ...(h.index === mappedIndex ? styles.thMapped : {}),
                  }}
                  title={
                    suggestedIndices.has(h.index)
                      ? "Columna sugerida por el asistente"
                      : undefined
                  }
                >
                  {h.name || <em style={{ opacity: 0.5 }}>(sin nombre)</em>}
                  {suggestedIndices.has(h.index) && (
                    <span style={styles.suggestBadge} aria-label="sugerencia">
                      ★
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sample_rows.map((row, ri) => (
              <tr key={ri} style={ri % 2 === 0 ? styles.rowEven : styles.rowOdd}>
                {row.map((cell, ci) => (
                  <td
                    key={ci}
                    style={{
                      ...styles.td,
                      ...(suggestedIndices.has(ci) ? styles.tdSuggested : {}),
                      ...(ci === mappedIndex ? styles.tdMapped : {}),
                    }}
                  >
                    {cell || <span style={{ opacity: 0.4 }}>—</span>}
                  </td>
                ))}
              </tr>
            ))}
            {sample_rows.length === 0 && (
              <tr>
                <td
                  colSpan={headers.length || 1}
                  style={{ ...styles.td, textAlign: "center", opacity: 0.5 }}
                >
                  Sin filas de muestra
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p style={styles.caption}>Mostrando hasta 5 filas de muestra.</p>
    </div>
  );
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "8px",
  },
  blockNote: {
    fontSize: "var(--font-size-xs)",
    color: "var(--color-primary)",
    backgroundColor: "var(--color-primary-light)",
    padding: "4px 10px",
    borderRadius: "var(--radius-sm)",
    border: "1px solid #bfdbfe",
  },
  discardNote: {
    fontSize: "var(--font-size-xs)",
    color: "#92400e",
    backgroundColor: "#fef3c7",
    padding: "4px 10px",
    borderRadius: "var(--radius-sm)",
  },
  warnNote: {
    fontSize: "var(--font-size-xs)",
    color: "#92400e",
    backgroundColor: "#fef3c7",
    padding: "4px 10px",
    borderRadius: "var(--radius-sm)",
  },
  tableWrapper: {
    overflowX: "auto" as const,
    border: "1px solid var(--color-border)",
    borderRadius: "var(--radius-md)",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse" as const,
    fontSize: "var(--font-size-sm)",
    tableLayout: "auto" as const,
  },
  th: {
    padding: "8px 12px",
    backgroundColor: "#f1f5f9",
    fontWeight: 600,
    color: "var(--color-text)",
    textAlign: "left" as const,
    whiteSpace: "nowrap" as const,
    borderBottom: "2px solid var(--color-border)",
    position: "relative" as const,
  },
  thSuggested: {
    backgroundColor: "#eff6ff",
    color: "var(--color-primary)",
    borderBottom: "2px solid var(--color-primary)",
  },
  thMapped: {
    backgroundColor: "#dcfce7",
    color: "#15803d",
    borderBottom: "2px solid #22c55e",
  },
  suggestBadge: {
    marginLeft: "4px",
    fontSize: "10px",
    color: "var(--color-primary)",
    verticalAlign: "middle",
  },
  rowEven: {
    backgroundColor: "var(--color-surface)",
  },
  rowOdd: {
    backgroundColor: "#fafafa",
  },
  td: {
    padding: "7px 12px",
    borderBottom: "1px solid var(--color-border)",
    color: "var(--color-text)",
    maxWidth: "200px",
    overflow: "hidden" as const,
    textOverflow: "ellipsis" as const,
    whiteSpace: "nowrap" as const,
  },
  tdSuggested: {
    backgroundColor: "#f0f7ff",
  },
  tdMapped: {
    backgroundColor: "#f0fdf4",
  },
  caption: {
    fontSize: "var(--font-size-xs)",
    color: "var(--color-text-disabled)",
    textAlign: "right" as const,
    paddingTop: "2px",
  },
} as const;
