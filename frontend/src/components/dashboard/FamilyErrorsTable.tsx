/**
 * FamilyErrorsTable — Top de Errores por Familia (T-5.2 Vista 1).
 */

import { useState, type JSX } from "react";
import type { FamiliesReportResponse } from "../../types/reporting";

interface Props {
  report: FamiliesReportResponse;
}

const numberFmt = new Intl.NumberFormat("es-ES");

export function FamilyErrorsTable({ report }: Props): JSX.Element {
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <section aria-label="Top de Errores por Familia" style={styles.section}>
      <h3 style={styles.heading}>Top de Errores por Familia</h3>

      {report.sin_clasificar_warning ? (
        <p style={styles.warning} data-testid="sin-clasificar-warning" role="alert">
          Hay códigos sin clasificar. Revise la familia &quot;Sin clasificar&quot; y actualice
          la taxonomía si es necesario.
        </p>
      ) : null}

      {report.families.length === 0 ? (
        <p style={styles.empty} data-testid="families-empty">
          No se encontraron errores clasificados en esta conciliación.
        </p>
      ) : (
        <div style={styles.tableWrap}>
        <table style={styles.table} data-testid="families-table">
          <thead>
            <tr>
              <th style={styles.th}>Familia</th>
              <th style={styles.thRight}>SKUs únicos</th>
              <th style={styles.thRight}>Errores</th>
              <th style={styles.th}>Códigos</th>
            </tr>
          </thead>
          <tbody>
            {report.families.map((family) => {
              const isOpen = expanded === family.code;
              return (
                <tr key={family.code} data-testid={`family-row-${family.code}`}>
                  <td style={styles.td}>
                    <button
                      type="button"
                      style={styles.familyButton}
                      aria-expanded={isOpen}
                      onClick={() =>
                        setExpanded(isOpen ? null : family.code)
                      }
                    >
                      {family.display_name}
                    </button>
                  </td>
                  <td style={styles.tdRight}>
                    {numberFmt.format(family.unique_skus)}
                  </td>
                  <td style={styles.tdRight}>
                    {numberFmt.format(family.total_errors)}
                  </td>
                  <td style={styles.td}>
                    {isOpen ? (
                      <ul style={styles.codeList} data-testid={`family-codes-${family.code}`}>
                        {family.codes.map((code) => (
                          <li key={code.code}>
                            <strong>{code.code}</strong>
                            {" · "}
                            {numberFmt.format(code.count)} — {code.message}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <span style={styles.codeSummary}>
                        {family.codes
                          .slice(0, 2)
                          .map((c) => c.code)
                          .join(", ")}
                        {family.codes.length > 2 ? "…" : ""}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      )}
    </section>
  );
}

const styles = {
  section: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "12px",
  },
  heading: {
    fontSize: "16px",
    fontWeight: 600,
    margin: 0,
    color: "var(--color-text)",
  },
  warning: {
    margin: 0,
    padding: "10px 12px",
    fontSize: "13px",
    color: "#92400e",
    backgroundColor: "#fef3c7",
    borderRadius: "var(--radius-md)",
    border: "1px solid #fcd34d",
  },
  empty: {
    margin: 0,
    fontSize: "13px",
    color: "var(--color-text-muted)",
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
    verticalAlign: "top" as const,
  },
  tdRight: {
    padding: "10px 12px",
    borderBottom: "1px solid var(--color-border)",
    textAlign: "right" as const,
    verticalAlign: "top" as const,
  },
  familyButton: {
    background: "none",
    border: "none",
    padding: 0,
    font: "inherit",
    color: "var(--color-primary)",
    cursor: "pointer",
    textAlign: "left" as const,
    textDecoration: "underline",
  },
  codeList: {
    margin: 0,
    paddingLeft: "18px",
    display: "flex",
    flexDirection: "column" as const,
    gap: "4px",
  },
  codeSummary: {
    color: "var(--color-text-muted)",
  },
} as const;
