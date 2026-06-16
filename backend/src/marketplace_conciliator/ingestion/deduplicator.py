"""Deduplication engine — spec 2.6 / RF-05 (T-4.2).

Policy per source role (applied after SKU normalisation):

  Any role:     filas idénticas byte a byte (tras normalizar sku_norm) →
                ``collapsed_identical`` (colapsar a 1 fila).
  ``occ_top``:  mismo sku_norm, datos distintos → ``kept_first``
                (primera ocurrencia, sin agregar).
  ``wm_feed``:  mismo sku_norm, stock distinto → ``kept_max_stock`` +
                ``stock_conflict = True``.  Si el stock coincide pero otros
                campos difieren → ``kept_first``.
  ``amazon_report``: la cardinalidad 1:N es legítima — solo se colapsan filas
                con MISMO (sku_norm + error_key_cols). Múltiples errores
                distintos para el mismo SKU NO son duplicados.

Restricciones de arquitectura:
  - Módulo PURO: sin I/O, sin imports del módulo ``platform`` (ADR-001).
  - Determinista: mismas entradas → mismas salidas.
  - Se ubica en ``ingestion`` para que ``ingestion/router.py`` pueda usarlo
    sin cruzar la frontera ``ingestion ↔ reconciliation`` (import-linter
    independence contract, ADR-001).  La lógica de negocio es de
    reconciliación, pero el artefacto se mueve al módulo correcto en T-4.6
    cuando el pipeline sea completamente asíncrono.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from marketplace_conciliator.ingestion.sku_normalizer import normalise_sku

# ── Internal sentinel column — removed from all returned DataFrames ──────────
_NORM_COL: str = "__sku_norm__"


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DuplicateFindingData:
    """Immutable value object that maps to one ``duplicate_findings`` DB row.

    See spec 2.10 and T-1.7 for the schema definition.
    """

    sku_norm: str
    occurrences: int
    resolution: str  # collapsed_identical | kept_first | kept_max_stock
    discarded_values: dict[str, Any]


@dataclass
class DeduplicationResult:
    """Result of deduplicating one source DataFrame.

    Attributes:
        dataframe:       Clean DataFrame (at most one row per sku_norm
                         after within-file deduplication).
        findings:        Audit records for every resolved duplicate group.
        stock_conflicts: Set of sku_norms where the MAX(stock) policy was
                         applied (``kept_max_stock`` resolution).

    """

    dataframe: pd.DataFrame
    findings: list[DuplicateFindingData] = field(default_factory=list)
    stock_conflicts: set[str] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def deduplicate_occ(df: pd.DataFrame, sku_col: str) -> DeduplicationResult:
    """Deduplicate OCC (Libro1) DataFrame — spec 2.6.

    Policy:
    - Filas completamente idénticas → ``collapsed_identical`` (keep 1).
    - Mismo ``sku_norm``, datos distintos → ``kept_first`` (primera ocurrencia).

    Args:
        df:       Source DataFrame (all dtypes str, as from ExcelParser).
        sku_col:  Name of the column containing SKU raw values.

    Returns:
        :class:`DeduplicationResult` with the deduplicated DataFrame and
        any findings for duplicate groups with more than one row.

    """
    df = _add_norm_col(df, sku_col)
    kept_indices: list[int] = []
    findings: list[DuplicateFindingData] = []

    for sku_norm, group in df.groupby(_NORM_COL, sort=False):
        if not isinstance(sku_norm, str) or not sku_norm:
            # Invalid / empty sku_norm — keep all rows, no deduplication
            kept_indices.extend(int(i) for i in group.index)
            continue

        if len(group) == 1:
            kept_indices.append(int(group.index[0]))
            continue

        compare_cols = [c for c in group.columns if c != _NORM_COL]
        unique_rows = group[compare_cols].drop_duplicates()

        if len(unique_rows) == 1:
            # All rows are byte-for-byte identical
            kept_indices.append(int(group.index[0]))
            findings.append(
                DuplicateFindingData(
                    sku_norm=sku_norm,
                    occurrences=len(group),
                    resolution="collapsed_identical",
                    discarded_values={"duplicate_count": len(group) - 1},
                ),
            )
        else:
            # Different data — keep the first occurrence (primera fila)
            kept_indices.append(int(group.index[0]))
            kept_row = group.iloc[0][compare_cols].to_dict()
            discarded_rows = group.iloc[1:][compare_cols].to_dict(orient="records")
            findings.append(
                DuplicateFindingData(
                    sku_norm=sku_norm,
                    occurrences=len(group),
                    resolution="kept_first",
                    discarded_values={
                        "kept_row": kept_row,
                        "discarded_rows": discarded_rows,
                    },
                ),
            )

    result_df = df.loc[kept_indices].drop(columns=[_NORM_COL]).reset_index(drop=True)
    return DeduplicationResult(dataframe=result_df, findings=findings)


def deduplicate_feed(
    df: pd.DataFrame,
    sku_col: str,
    stock_col: str | None,
) -> DeduplicationResult:
    """Deduplicate WM Feed DataFrame — spec 2.6.

    Policy:
    - Filas completamente idénticas → ``collapsed_identical``.
    - Mismo ``sku_norm``, stock distinto → ``kept_max_stock`` +
      ``stock_conflict = True``.
    - Mismo ``sku_norm``, mismo stock, otras columnas distintas →
      ``kept_first``.

    Args:
        df:        Source DataFrame (dtype str, as from CsvParser).
        sku_col:   Column name for SKU values.
        stock_col: Column name for stock values, or ``None`` if not mapped.

    """
    df = _add_norm_col(df, sku_col)
    kept_rows: list[pd.Series] = []
    findings: list[DuplicateFindingData] = []
    stock_conflicts: set[str] = set()

    for sku_norm, group in df.groupby(_NORM_COL, sort=False):
        if not isinstance(sku_norm, str) or not sku_norm:
            kept_rows.extend(group.iloc[i] for i in range(len(group)))
            continue

        if len(group) == 1:
            kept_rows.append(group.iloc[0])
            continue

        compare_cols = [c for c in group.columns if c != _NORM_COL]
        unique_rows = group[compare_cols].drop_duplicates()

        if len(unique_rows) == 1:
            # Perfectly identical rows
            kept_rows.append(group.iloc[0])
            findings.append(
                DuplicateFindingData(
                    sku_norm=sku_norm,
                    occurrences=len(group),
                    resolution="collapsed_identical",
                    discarded_values={"duplicate_count": len(group) - 1},
                ),
            )
            continue

        # Rows differ — check stock column
        if stock_col and stock_col in group.columns:
            stock_values = group[stock_col].apply(_parse_stock)
            valid_stocks = stock_values.dropna()

            if len(valid_stocks.unique()) > 1:
                # Stock conflict → MAX policy (spec 2.6) — nunca se suma
                max_idx = int(stock_values.idxmax())
                kept_rows.append(group.loc[max_idx])
                stock_conflicts.add(sku_norm)
                all_stock_vals = [
                    v for v in stock_values.tolist() if v is not None
                ]
                findings.append(
                    DuplicateFindingData(
                        sku_norm=sku_norm,
                        occurrences=len(group),
                        resolution="kept_max_stock",
                        discarded_values={"stock_values": all_stock_vals},
                    ),
                )
                continue

        # Same stock (or no stock col) but other columns differ → kept_first
        kept_rows.append(group.iloc[0])
        findings.append(
            DuplicateFindingData(
                sku_norm=sku_norm,
                occurrences=len(group),
                resolution="kept_first",
                discarded_values={
                    "kept_row": group.iloc[0][compare_cols].to_dict(),
                    "discarded_rows": group.iloc[1:][compare_cols].to_dict(
                        orient="records",
                    ),
                },
            ),
        )

    if kept_rows:
        result_df = (
            pd.DataFrame(kept_rows)
            .drop(columns=[_NORM_COL])
            .reset_index(drop=True)
        )
    else:
        result_df = (
            df.drop(columns=[_NORM_COL]).iloc[0:0].reset_index(drop=True)
        )

    return DeduplicationResult(
        dataframe=result_df,
        findings=findings,
        stock_conflicts=stock_conflicts,
    )


def deduplicate_amazon_errors(
    df: pd.DataFrame,
    sku_col: str,
    error_key_cols: list[str],
) -> DeduplicationResult:
    """Deduplicate Amazon report errors — spec 2.6.

    Policy:
    - ONLY collapses rows that are IDENTICAL on
      ``(sku_norm + all error_key_cols)``.
    - Multiple DIFFERENT error rows for the same ``sku_norm`` are NOT
      duplicates (legítima cardinalidad 1:N — evidencia real: hasta 11
      errores por SKU, spec 2.2.3).
    - Resolution for collapsed rows: ``collapsed_identical``.

    Args:
        df:             DataFrame produced by BlockLocator (error block rows).
        sku_col:        Column name for SKU values.
        error_key_cols: Columns that define error row uniqueness
                        (typically: error_code, error_message, affected_field).

    """
    df = _add_norm_col(df, sku_col)
    findings: list[DuplicateFindingData] = []

    # Deduplication key: sku_norm + present error key columns
    key_cols_present = [c for c in error_key_cols if c in df.columns]

    if not key_cols_present:
        # No error key cols → cannot deduplicate errors; return as-is
        result_df = df.drop(columns=[_NORM_COL]).reset_index(drop=True)
        return DeduplicationResult(dataframe=result_df, findings=findings)

    dedup_key = [_NORM_COL, *key_cols_present]

    # Build deduplication mask: keep only the first occurrence of each unique key
    seen_keys: set[tuple[str, ...]] = set()
    kept_indices: list[int] = []
    # Track how many identical rows were collapsed per sku_norm
    collapsed_per_sku: dict[str, int] = {}

    for idx, row in df.iterrows():
        key = tuple(str(row.get(c, "") or "") for c in dedup_key)
        if key not in seen_keys:
            seen_keys.add(key)
            kept_indices.append(int(idx))
        else:
            sku_n = str(row.get(_NORM_COL, "") or "")
            if sku_n:
                collapsed_per_sku[sku_n] = collapsed_per_sku.get(sku_n, 0) + 1

    for sku_n, collapsed_count in collapsed_per_sku.items():
        if collapsed_count > 0:
            findings.append(
                DuplicateFindingData(
                    sku_norm=sku_n,
                    occurrences=collapsed_count + 1,
                    resolution="collapsed_identical",
                    discarded_values={
                        "identical_error_rows_collapsed": collapsed_count,
                    },
                ),
            )

    result_df = (
        df.loc[kept_indices].drop(columns=[_NORM_COL]).reset_index(drop=True)
    )
    return DeduplicationResult(dataframe=result_df, findings=findings)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _add_norm_col(df: pd.DataFrame, sku_col: str) -> pd.DataFrame:
    """Return a copy of *df* with a ``__sku_norm__`` helper column appended."""
    df = df.copy()

    def _norm(v: object) -> str:
        raw = str(v) if v is not None else ""
        result = normalise_sku(raw)
        return result.value or ""

    df[_NORM_COL] = df[sku_col].apply(_norm)
    return df


def _parse_stock(value: object) -> float | None:
    """Parse a cell value to float, returning ``None`` for non-numeric input."""
    if value is None:
        return None
    try:
        return float(str(value).strip().replace(",", "."))
    except (ValueError, TypeError):
        return None
