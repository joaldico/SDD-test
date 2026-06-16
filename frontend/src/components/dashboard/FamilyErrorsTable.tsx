/**
 * FamilyErrorsTable — Errores por Familia with familia→código→SKU drill-down (T-5.2 / T-5.4).
 */

import { Fragment, useEffect, useState, type JSX } from "react";
import type {
  FamiliesReportResponse,
  SkuDetailResponse,
} from "../../types/reporting";
import {
  REPORT_PAGE_SIZE,
  TablePagination,
  totalPagesFromCount,
} from "./TablePagination";

interface Props {
  report: FamiliesReportResponse;
  onFetchSkusForCode: (
    familyCode: string,
    errorCode: string,
    page?: number,
  ) => Promise<SkuDetailResponse>;
}

const numberFmt = new Intl.NumberFormat("es-ES");

export function FamilyErrorsTable({
  report,
  onFetchSkusForCode,
}: Props): JSX.Element {
  const [familyPage, setFamilyPage] = useState(1);
  const [expandedFamily, setExpandedFamily] = useState<string | null>(null);
  const [expandedCode, setExpandedCode] = useState<string | null>(null);
  const [skuCache, setSkuCache] = useState<Record<string, SkuDetailResponse>>({});
  const [skuPageByCode, setSkuPageByCode] = useState<Record<string, number>>({});
  const [loadingCode, setLoadingCode] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const cacheKey = (familyCode: string, errorCode: string): string =>
    `${familyCode}:${errorCode}`;

  const skuCacheKey = (
    familyCode: string,
    errorCode: string,
    page: number,
  ): string => `${cacheKey(familyCode, errorCode)}:p${page}`;

  const familyTotalPages = totalPagesFromCount(
    report.families.length,
    REPORT_PAGE_SIZE,
  );
  const familyOffset = (familyPage - 1) * REPORT_PAGE_SIZE;
  const paginatedFamilies = report.families.slice(
    familyOffset,
    familyOffset + REPORT_PAGE_SIZE,
  );

  useEffect(() => {
    setExpandedFamily(null);
    setExpandedCode(null);
    setLoadError(null);
  }, [familyPage]);

  const handleFamilyPageChange = (nextPage: number): void => {
    setFamilyPage(nextPage);
  };

  const handleFamilyToggle = (familyCode: string): void => {
    if (expandedFamily === familyCode) {
      setExpandedFamily(null);
      setExpandedCode(null);
      return;
    }
    setExpandedFamily(familyCode);
    setExpandedCode(null);
    setLoadError(null);
  };

  const loadSkus = async (
    familyCode: string,
    errorCode: string,
    page: number,
  ): Promise<void> => {
    const key = skuCacheKey(familyCode, errorCode, page);
    setLoadingCode(key);
    setLoadError(null);

    try {
      const response = await onFetchSkusForCode(familyCode, errorCode, page);
      setSkuCache((prev) => ({ ...prev, [key]: response }));
      setSkuPageByCode((prev) => ({ ...prev, [cacheKey(familyCode, errorCode)]: page }));
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "No se pudieron cargar los SKUs";
      setLoadError(message);
    } finally {
      setLoadingCode(null);
    }
  };

  const handleCodeToggle = async (
    familyCode: string,
    errorCode: string,
  ): Promise<void> => {
    const codeKey = cacheKey(familyCode, errorCode);
    if (expandedCode === codeKey) {
      setExpandedCode(null);
      return;
    }

    setExpandedCode(codeKey);
    setLoadError(null);

    const page = skuPageByCode[codeKey] ?? 1;
    const cached = skuCache[skuCacheKey(familyCode, errorCode, page)];
    if (cached) return;

    await loadSkus(familyCode, errorCode, page);
  };

  const handleSkuPageChange = async (
    familyCode: string,
    errorCode: string,
    nextPage: number,
  ): Promise<void> => {
    const codeKey = cacheKey(familyCode, errorCode);
    setSkuPageByCode((prev) => ({ ...prev, [codeKey]: nextPage }));

    const cached = skuCache[skuCacheKey(familyCode, errorCode, nextPage)];
    if (cached) return;

    await loadSkus(familyCode, errorCode, nextPage);
  };

  return (
    <section aria-label="Errores por Familia" style={styles.section}>
      <h3 style={styles.heading}>Errores por Familia</h3>
      <p style={styles.hint}>
        Despliega una familia para ver sus códigos y selecciona un código para
        listar los SKUs afectados.
      </p>

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
        <>
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
                {paginatedFamilies.map((family) => {
                  const isFamilyOpen = expandedFamily === family.code;
                  return (
                    <Fragment key={family.code}>
                      <tr data-testid={`family-row-${family.code}`}>
                        <td style={styles.td}>
                          <button
                            type="button"
                            style={styles.familyButton}
                            aria-expanded={isFamilyOpen}
                            onClick={() => handleFamilyToggle(family.code)}
                          >
                            {isFamilyOpen ? "▾" : "▸"} {family.display_name}
                          </button>
                        </td>
                        <td style={styles.tdRight}>
                          {numberFmt.format(family.unique_skus)}
                        </td>
                        <td style={styles.tdRight}>
                          {numberFmt.format(family.total_errors)}
                        </td>
                        <td style={styles.td}>
                          <span style={styles.codeSummary}>
                            {family.codes.length}{" "}
                            {family.codes.length === 1 ? "código" : "códigos"}
                          </span>
                        </td>
                      </tr>

                      {isFamilyOpen ? (
                        <tr>
                          <td colSpan={4} style={styles.detailCell}>
                            <div
                              style={styles.codePanel}
                              data-testid={`family-codes-${family.code}`}
                            >
                              <table style={styles.innerTable}>
                                <thead>
                                  <tr>
                                    <th style={styles.innerTh}>Código</th>
                                    <th style={styles.innerTh}>Mensaje</th>
                                    <th style={styles.innerThRight}>Errores</th>
                                    <th style={styles.innerTh}>SKUs</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {family.codes.map((codeRow) => {
                                    const codeKey = cacheKey(family.code, codeRow.code);
                                    const isCodeOpen = expandedCode === codeKey;
                                    const skuPage = skuPageByCode[codeKey] ?? 1;
                                    const skuResponse =
                                      skuCache[skuCacheKey(family.code, codeRow.code, skuPage)];
                                    const skus = skuResponse?.items ?? [];
                                    const skuTotalPages = skuResponse
                                      ? totalPagesFromCount(
                                          skuResponse.total,
                                          skuResponse.page_size,
                                        )
                                      : 1;
                                    const isLoading =
                                      loadingCode ===
                                      skuCacheKey(family.code, codeRow.code, skuPage);

                                    return (
                                      <Fragment key={codeRow.code}>
                                        <tr
                                          data-testid={`code-row-${family.code}-${codeRow.code}`}
                                        >
                                          <td style={styles.innerTd}>
                                            <button
                                              type="button"
                                              style={styles.codeButton}
                                              aria-expanded={isCodeOpen}
                                              onClick={() =>
                                                void handleCodeToggle(
                                                  family.code,
                                                  codeRow.code,
                                                )
                                              }
                                            >
                                              {isCodeOpen ? "▾" : "▸"}{" "}
                                              <strong>{codeRow.code}</strong>
                                            </button>
                                          </td>
                                          <td style={styles.innerTd}>{codeRow.message}</td>
                                          <td style={styles.innerTdRight}>
                                            {numberFmt.format(codeRow.count)}
                                          </td>
                                          <td style={styles.innerTd}>
                                            {isLoading ? (
                                              <span style={styles.muted}>Cargando…</span>
                                            ) : isCodeOpen && skuResponse ? (
                                              <span style={styles.muted}>
                                                {numberFmt.format(skuResponse.total)} SKU
                                                {skuResponse.total === 1 ? "" : "s"}
                                              </span>
                                            ) : (
                                              <span style={styles.muted}>Ver SKUs</span>
                                            )}
                                          </td>
                                        </tr>

                                        {isCodeOpen ? (
                                          <tr>
                                            <td colSpan={4} style={styles.skuCell}>
                                              {loadError && expandedCode === codeKey ? (
                                                <p style={styles.errorText}>{loadError}</p>
                                              ) : isLoading ? (
                                                <p
                                                  style={styles.muted}
                                                  data-testid={`sku-loading-${family.code}-${codeRow.code}`}
                                                >
                                                  Cargando SKUs afectados…
                                                </p>
                                              ) : skuResponse && skus.length === 0 ? (
                                                <p
                                                  style={styles.muted}
                                                  data-testid={`sku-empty-${family.code}-${codeRow.code}`}
                                                >
                                                  No hay SKUs para este código.
                                                </p>
                                              ) : skuResponse ? (
                                                <>
                                                  <ul
                                                    style={styles.skuList}
                                                    data-testid={`sku-list-${family.code}-${codeRow.code}`}
                                                  >
                                                    {skus.map((sku) => (
                                                      <li
                                                        key={`${sku.sku_norm}-${sku.error_code}`}
                                                        data-testid={`sku-item-${sku.sku_norm}`}
                                                      >
                                                        <span style={styles.skuCode}>
                                                          {sku.sku_raw}
                                                        </span>
                                                        {" — "}
                                                        {sku.error_message}
                                                      </li>
                                                    ))}
                                                  </ul>
                                                  <TablePagination
                                                    page={skuPage}
                                                    totalPages={skuTotalPages}
                                                    onPrevious={() =>
                                                      void handleSkuPageChange(
                                                        family.code,
                                                        codeRow.code,
                                                        Math.max(1, skuPage - 1),
                                                      )
                                                    }
                                                    onNext={() =>
                                                      void handleSkuPageChange(
                                                        family.code,
                                                        codeRow.code,
                                                        Math.min(
                                                          skuTotalPages,
                                                          skuPage + 1,
                                                        ),
                                                      )
                                                    }
                                                    testId={`sku-pagination-${family.code}-${codeRow.code}`}
                                                  />
                                                </>
                                              ) : null}
                                            </td>
                                          </tr>
                                        ) : null}
                                      </Fragment>
                                    );
                                  })}
                                </tbody>
                              </table>
                            </div>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>

          <TablePagination
            page={familyPage}
            totalPages={familyTotalPages}
            onPrevious={() =>
              handleFamilyPageChange(Math.max(1, familyPage - 1))
            }
            onNext={() =>
              handleFamilyPageChange(Math.min(familyTotalPages, familyPage + 1))
            }
            testId="families-pagination"
          />
        </>
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
  hint: {
    margin: 0,
    fontSize: "13px",
    color: "var(--color-text-muted)",
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
  detailCell: {
    padding: 0,
    backgroundColor: "#f8fafc",
    borderBottom: "1px solid var(--color-border)",
  },
  codePanel: {
    padding: "12px 16px",
  },
  innerTable: {
    width: "100%",
    borderCollapse: "collapse" as const,
    fontSize: "12px",
  },
  innerTh: {
    textAlign: "left" as const,
    padding: "8px 10px",
    borderBottom: "1px solid var(--color-border)",
    fontWeight: 600,
    color: "var(--color-text-muted)",
  },
  innerThRight: {
    textAlign: "right" as const,
    padding: "8px 10px",
    borderBottom: "1px solid var(--color-border)",
    fontWeight: 600,
    color: "var(--color-text-muted)",
  },
  innerTd: {
    padding: "8px 10px",
    borderBottom: "1px solid var(--color-border)",
    verticalAlign: "top" as const,
  },
  innerTdRight: {
    padding: "8px 10px",
    borderBottom: "1px solid var(--color-border)",
    textAlign: "right" as const,
    verticalAlign: "top" as const,
  },
  skuCell: {
    padding: "8px 10px 12px 28px",
    backgroundColor: "#fff",
    borderBottom: "1px solid var(--color-border)",
  },
  familyButton: {
    background: "none",
    border: "none",
    padding: 0,
    font: "inherit",
    color: "var(--color-primary)",
    cursor: "pointer",
    textAlign: "left" as const,
    fontWeight: 600,
  },
  codeButton: {
    background: "none",
    border: "none",
    padding: 0,
    font: "inherit",
    color: "var(--color-text)",
    cursor: "pointer",
    textAlign: "left" as const,
  },
  codeSummary: {
    color: "var(--color-text-muted)",
  },
  skuList: {
    margin: 0,
    paddingLeft: "18px",
    display: "flex",
    flexDirection: "column" as const,
    gap: "6px",
  },
  skuCode: {
    fontFamily: "monospace",
    fontSize: "12px",
    fontWeight: 600,
  },
  muted: {
    color: "var(--color-text-muted)",
    margin: 0,
  },
  errorText: {
    margin: 0,
    fontSize: "12px",
    color: "#dc2626",
  },
} as const;
