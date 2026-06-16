/**
 * TaxonomiaPage — T-5.6 admin UI for error code → family reassignment (RF-14).
 */

import { useCallback, useEffect, useState, type JSX } from "react";

import { getErrorTaxonomy, patchErrorCodeFamily } from "../api/taxonomy";
import type { ErrorCodeCatalogItem, ErrorFamilyItem } from "../types/taxonomy";

type ScreenState =
  | { kind: "loading" }
  | {
      kind: "ready";
      families: ErrorFamilyItem[];
      codes: ErrorCodeCatalogItem[];
    }
  | { kind: "error"; message: string };

export function TaxonomiaPage(): JSX.Element {
  const [screen, setScreen] = useState<ScreenState>({ kind: "loading" });
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [savingCode, setSavingCode] = useState<string | null>(null);

  const loadCatalog = useCallback(async () => {
    setScreen({ kind: "loading" });
    try {
      const data = await getErrorTaxonomy();
      setScreen({ kind: "ready", families: data.families, codes: data.codes });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "No se pudo cargar la taxonomía";
      setScreen({ kind: "error", message });
    }
  }, []);

  useEffect(() => {
    void loadCatalog();
  }, [loadCatalog]);

  const handleFamilyChange = async (code: string, familyCode: string) => {
    if (screen.kind !== "ready") return;

    setSavingCode(code);
    setStatusMessage(null);
    try {
      const updated = await patchErrorCodeFamily(code, { family_code: familyCode });
      setScreen({
        kind: "ready",
        families: screen.families,
        codes: screen.codes.map((item) =>
          item.code === code ? { ...item, family_code: updated.family_code } : item,
        ),
      });
      const familyLabel =
        screen.families.find((f) => f.code === updated.family_code)?.display_name ??
        updated.family_code;
      setStatusMessage(`Código ${code} reasignado a ${familyLabel}.`);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "No se pudo actualizar la familia";
      setStatusMessage(message);
      void loadCatalog();
    } finally {
      setSavingCode(null);
    }
  };

  if (screen.kind === "loading") {
    return (
      <div style={styles.page}>
        <p role="status">Cargando taxonomía…</p>
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

  return (
    <div style={styles.page}>
      <header style={styles.header}>
        <h1 style={styles.title}>Taxonomía de errores</h1>
        <p style={styles.subtitle}>
          Reasigna códigos de error de Amazon a familias de negocio. Los cambios se
          reflejan de inmediato en el informe (Vista 1).
        </p>
      </header>

      {statusMessage && (
        <p role="status" style={styles.status}>
          {statusMessage}
        </p>
      )}

      <div style={styles.tableWrap}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Código</th>
              <th style={styles.th}>Mensaje canónico</th>
              <th style={styles.th}>Familia</th>
            </tr>
          </thead>
          <tbody>
            {screen.codes.map((item) => (
              <tr key={item.code}>
                <td style={styles.td}>
                  <code>{item.code}</code>
                </td>
                <td style={styles.td}>
                  {item.canonical_message ?? "—"}
                </td>
                <td style={styles.td}>
                  <select
                    aria-label={`Familia del código ${item.code}`}
                    value={item.family_code}
                    disabled={savingCode === item.code}
                    onChange={(event) => {
                      void handleFamilyChange(item.code, event.target.value);
                    }}
                    style={styles.select}
                  >
                    {screen.families.map((family) => (
                      <option key={family.code} value={family.code}>
                        {family.display_name}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const styles = {
  page: {
    padding: "32px",
    maxWidth: "960px",
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
  status: {
    padding: "12px 16px",
    marginBottom: "16px",
    backgroundColor: "var(--color-bg-subtle)",
    borderRadius: "var(--radius-sm)",
    fontSize: "14px",
  },
  tableWrap: {
    overflowX: "auto" as const,
    border: "1px solid var(--color-border)",
    borderRadius: "var(--radius-md)",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse" as const,
    fontSize: "14px",
  },
  th: {
    textAlign: "left" as const,
    padding: "12px 16px",
    backgroundColor: "var(--color-bg-subtle)",
    borderBottom: "1px solid var(--color-border)",
    fontWeight: 600,
  },
  td: {
    padding: "12px 16px",
    borderBottom: "1px solid var(--color-border)",
    verticalAlign: "middle" as const,
  },
  select: {
    minWidth: "220px",
    padding: "6px 8px",
    fontSize: "14px",
  },
} as const;
