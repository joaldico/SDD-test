/**
 * TablePagination — stable prev/next controls for report tables (T-5.2 DoD).
 */

import type { JSX } from "react";

export const REPORT_PAGE_SIZE = 50;

interface Props {
  page: number;
  totalPages: number;
  onPrevious: () => void;
  onNext: () => void;
  testId?: string;
}

export function TablePagination({
  page,
  totalPages,
  onPrevious,
  onNext,
  testId = "table-pagination",
}: Props): JSX.Element | null {
  if (totalPages <= 1) return null;

  return (
    <nav style={styles.pagination} aria-label="Paginación" data-testid={testId}>
      <button
        type="button"
        style={styles.button}
        disabled={page <= 1}
        onClick={onPrevious}
        data-testid={`${testId}-prev`}
      >
        Anterior
      </button>
      <span style={styles.info} data-testid={`${testId}-info`}>
        Página {page} de {totalPages}
      </span>
      <button
        type="button"
        style={styles.button}
        disabled={page >= totalPages}
        onClick={onNext}
        data-testid={`${testId}-next`}
      >
        Siguiente
      </button>
    </nav>
  );
}

export function totalPagesFromCount(total: number, pageSize: number): number {
  return Math.max(1, Math.ceil(total / pageSize));
}

const styles = {
  pagination: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "16px",
    marginTop: "12px",
    fontSize: "13px",
  },
  button: {
    padding: "6px 14px",
    fontSize: "13px",
    borderRadius: "var(--radius-md)",
    border: "1px solid var(--color-border)",
    backgroundColor: "var(--color-surface)",
    color: "var(--color-text)",
    cursor: "pointer",
  },
  info: {
    color: "var(--color-text-muted)",
    fontVariantNumeric: "tabular-nums",
  },
} as const;
