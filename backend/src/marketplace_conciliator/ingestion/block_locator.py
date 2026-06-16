"""BlockLocator -- finds structured data blocks inside parsed Excel sheets (T-3.4).

Handles two specific layouts:
  1. "Resumen de procesamiento" sheet (Amazon processing summary):
     - Locates the section titled "Errores y advertencias por SKU" (EB-02).
     - Takes the immediately-following row as column headers.
     - Returns a sub-DataFrame of the block's data rows.
     - Raises BlockNotFoundError when the title is absent (EB-03).

  2. "Plantilla" sheet (Amazon upload template):
     - Has a *double header*: row 3 = group labels, row 4 = human-readable
       column labels, row 5 = technical attribute names.
     - ExcelParser reads row 1 (settings metadata) as DF column names, so
       the human-readable labels live at DF index 2 (= sheet row 4).
     - Discards the Amazon example row (contains 'ABC123' in the SKU column,
       EB-04) and counts it in discarded_rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Case-insensitive fragment to match the block title (EB-02)
_BLOCK_TITLE_FRAGMENT: str = "errores y advertencias por sku"

# Amazon's canonical example SKU that marks a placeholder / example row (EB-04)
_EXAMPLE_SKU_MARKER: str = "ABC123"

# Within ExcelParser output for the Plantilla sheet:
#   - row 1 (sheet) → DF column names (settings metadata — not useful)
#   - row 2 (sheet) → DF index 0  (general warning text)
#   - row 3 (sheet) → DF index 1  (group category labels — merged cells)
#   - row 4 (sheet) → DF index 2  ← human-readable column labels (USE THIS)
#   - row 5 (sheet) → DF index 3  (technical attribute names)
#   - row 6 (sheet) → DF index 4  (example row — ABC123)
#   - row 7+ (sheet) → DF index 5+ (actual data)
_PLANTILLA_LABEL_DF_INDEX: int = 2   # DF index that holds human-readable labels
_PLANTILLA_DATA_DF_INDEX: int = 5    # DF index where actual data starts (after example row)

# Column name of the SKU in the Plantilla human-readable label row
_PLANTILLA_SKU_LABEL: str = "SKU"

# In ExcelParser, header row = sheet row 1, so: sheet_row = df_index + 2
_DF_TO_SHEET_ROW_OFFSET: int = 2


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class BlockNotFoundError(ValueError):
    """Raised when the block title is not found in the DataFrame (EB-03)."""


# ---------------------------------------------------------------------------
# Result value object
# ---------------------------------------------------------------------------


@dataclass
class LocatedBlock:
    """Result of a successful block location.

    Attributes:
        dataframe:       Extracted block data with proper column names.
        title_row:       1-indexed sheet row where the block title was found.
        data_start_row:  1-indexed sheet row where data rows begin.
        sku_column:      Name of the column containing SKU values, or None.
        discarded_rows:  Count of rows discarded (e.g. Amazon example rows).
        warnings:        Non-fatal issues discovered during location.

    """

    dataframe: pd.DataFrame
    title_row: int
    data_start_row: int
    sku_column: str | None
    discarded_rows: int = 0
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# BlockLocator
# ---------------------------------------------------------------------------


class BlockLocator:
    """Locates structured blocks in parsed Excel DataFrames.

    All input DataFrames are expected to have ``object`` (str) dtype columns,
    as produced by :class:`~marketplace_conciliator.ingestion.excel_parser.ExcelParser`.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def locate_errors_block(self, df: pd.DataFrame) -> LocatedBlock:
        """Find the 'Errores y advertencias por SKU' block in a sheet DataFrame.

        Scans all rows looking for a cell that matches ``_BLOCK_TITLE_FRAGMENT``
        (case-insensitive, after stripping NBSP / extra whitespace).  The row
        immediately after the title is used as column headers; the rows after
        that are the block's data.

        Args:
            df: Full-sheet DataFrame produced by ExcelParser (row 1 = col names).

        Returns:
            :class:`LocatedBlock` with the extracted sub-DataFrame.

        Raises:
            BlockNotFoundError: If the title row cannot be found (EB-03).

        """
        import pandas as pd  # noqa: PLC0415

        title_df_idx: int | None = None

        for idx in range(len(df)):
            row_vals = df.iloc[idx].tolist()
            for cell in row_vals:
                normalized = _normalize_cell(cell)
                if _BLOCK_TITLE_FRAGMENT in normalized:
                    title_df_idx = idx
                    break
            if title_df_idx is not None:
                break

        if title_df_idx is None:
            msg = (
                "Block title 'Errores y advertencias por SKU' not found in the DataFrame. "
                "Make sure you are parsing the correct sheet (EB-03)."
            )
            raise BlockNotFoundError(msg)

        # The row right after the title contains the column headers
        header_df_idx = title_df_idx + 1
        data_df_idx = title_df_idx + 2

        if header_df_idx >= len(df):
            msg = "Block title found but no header row follows it."
            raise BlockNotFoundError(msg)

        # Build column names from the header row
        raw_headers: list[str] = [
            _normalize_cell_as_header(v) for v in df.iloc[header_df_idx].tolist()
        ]

        # Slice the data rows
        if data_df_idx >= len(df):
            data_df = pd.DataFrame(columns=raw_headers)
        else:
            data_rows = df.iloc[data_df_idx:].to_numpy(dtype=object).tolist()
            data_df = pd.DataFrame(data_rows, columns=raw_headers)

        # Identify SKU column (last column whose name normalizes to "sku")
        sku_col = _find_sku_column(raw_headers)

        # Convert DF indices to 1-indexed sheet rows
        title_sheet_row = title_df_idx + _DF_TO_SHEET_ROW_OFFSET
        data_start_sheet_row = data_df_idx + _DF_TO_SHEET_ROW_OFFSET

        return LocatedBlock(
            dataframe=data_df,
            title_row=title_sheet_row,
            data_start_row=data_start_sheet_row,
            sku_column=sku_col,
        )

    def parse_plantilla(self, df: pd.DataFrame) -> LocatedBlock:
        """Parse the 'Plantilla' (Amazon upload template) sheet DataFrame.

        Handles the double-header layout:
        - DF index 2 (sheet row 4) → human-readable column labels → used as column names.
        - DF index 3 (sheet row 5) → technical attribute names → discarded.
        - DF index 4 (sheet row 6) → Amazon example row (ABC123) → discarded.
        - DF index 5+              → actual product data.

        Args:
            df: Full Plantilla-sheet DataFrame produced by ExcelParser.

        Returns:
            :class:`LocatedBlock` with column names from the human-readable
            label row and data starting after the example row.

        """
        import pandas as pd  # noqa: PLC0415

        # Extract human-readable column labels (sheet row 4 = DF index 2)
        label_row = df.iloc[_PLANTILLA_LABEL_DF_INDEX].tolist()
        col_names: list[str] = [_normalize_cell_as_header(v) for v in label_row]

        # Data rows start at DF index 5 (after double header + example row)
        raw_data_df = df.iloc[_PLANTILLA_DATA_DF_INDEX:].copy()
        raw_data_df.columns = pd.Index(col_names[: len(raw_data_df.columns)])
        raw_data_df = raw_data_df.reset_index(drop=True)

        # Identify SKU column
        sku_col = _find_sku_column(col_names)

        # Discard remaining example rows (e.g. ABC123 might appear in data)
        discarded = 0
        if sku_col and sku_col in raw_data_df.columns:
            mask = raw_data_df[sku_col].apply(
                lambda v: _normalize_cell(v) == _EXAMPLE_SKU_MARKER.lower(),
            )
            discarded = int(mask.sum())
            raw_data_df = raw_data_df[~mask].reset_index(drop=True)

        # Also count the example row at DF index 4 (sheet row 6) — it was
        # unconditionally skipped, so add 1 if the DF had enough rows.
        if len(df) > _PLANTILLA_DATA_DF_INDEX - 1:
            example_row_val = df.iloc[_PLANTILLA_DATA_DF_INDEX - 1]
            if sku_col:
                # Find the column position matching the SKU label
                try:
                    sku_pos = col_names.index(sku_col)
                    cell_val = (
                        str(example_row_val.iloc[sku_pos])
                        if sku_pos < len(example_row_val)
                        else ""
                    )
                    if _normalize_cell(cell_val) == _EXAMPLE_SKU_MARKER.lower():
                        discarded += 1
                except (ValueError, IndexError):
                    pass

        title_sheet_row = _PLANTILLA_LABEL_DF_INDEX + _DF_TO_SHEET_ROW_OFFSET
        data_start_sheet_row = _PLANTILLA_DATA_DF_INDEX + _DF_TO_SHEET_ROW_OFFSET

        return LocatedBlock(
            dataframe=raw_data_df,
            title_row=title_sheet_row,
            data_start_row=data_start_sheet_row,
            sku_column=sku_col,
            discarded_rows=discarded,
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _normalize_cell(value: object) -> str:
    """Return a lowercase, stripped string from any cell value.

    Replaces non-breaking spaces (U+00A0) so that title matching is robust
    to the NBSP characters Amazon sometimes embeds in template cells.
    """
    if value is None:
        return ""
    return str(value).replace("\u00a0", " ").strip().lower()


def _normalize_cell_as_header(value: object) -> str:
    """Return a header string preserving original casing, stripping only whitespace."""
    if value is None:
        return ""
    return str(value).replace("\u00a0", " ").strip()


def _find_sku_column(columns: list[str]) -> str | None:
    """Return the name of the column that most likely contains SKU values.

    Priority (highest to lowest):
      1. Exact (case-insensitive) match 'sku'.
      2. Column name starts with 'sku'.
      3. Last column whose name contains 'sku'.
    """
    exact = [c for c in columns if c.lower() == "sku"]
    if exact:
        return exact[0]
    starts = [c for c in columns if c.lower().startswith("sku")]
    if starts:
        return starts[0]
    contains = [c for c in columns if "sku" in c.lower()]
    if contains:
        return contains[-1]  # prefer the last matching column per DoD
    return None
