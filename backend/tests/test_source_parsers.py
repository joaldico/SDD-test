"""T-3.2 / T-3.3 — Tests for SourceParser, CsvParser, and ExcelParser.

Written BEFORE the implementation (TDD).  All assertions run against the
canonical fixtures installed in T-1.2 (tests/fixtures/).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from marketplace_conciliator.ingestion.csv_parser import CsvParser
from marketplace_conciliator.ingestion.excel_parser import ExcelParser
from marketplace_conciliator.ingestion.source_parser import (
    SourceParser,
    UnsupportedFormatError,
)

FIXTURES = Path(__file__).parent / "fixtures"
CSV_FIXTURE = FIXTURES / "wavemarket_fullstock_anonymized.csv"
XLSX_FIXTURE = FIXTURES / "occ_top_sales_anonymized.xlsx"
XLSM_FIXTURE = FIXTURES / "amazon_processing_summary_anonymized.xlsm"


# ---------------------------------------------------------------------------
# SourceParser protocol smoke-test: CsvParser and ExcelParser satisfy it
# ---------------------------------------------------------------------------
def test_csv_parser_satisfies_protocol() -> None:
    parser: SourceParser = CsvParser()  # type: ignore[assignment]  # structural
    assert callable(getattr(parser, "parse", None))
    assert callable(getattr(parser, "list_sheets", None))


def test_excel_parser_satisfies_protocol() -> None:
    parser: SourceParser = ExcelParser()  # type: ignore[assignment]
    assert callable(getattr(parser, "parse", None))
    assert callable(getattr(parser, "list_sheets", None))


# ---------------------------------------------------------------------------
# T-3.2 — CsvParser
# ---------------------------------------------------------------------------
class TestCsvParser:
    def setup_method(self) -> None:
        self.parser = CsvParser()

    def test_fixture_row_count(self) -> None:
        """The fullstock fixture must have exactly 4 156 data rows (T-1.2)."""
        result = self.parser.parse(CSV_FIXTURE)
        assert len(result.dataframe) == 4156

    def test_all_columns_are_str_dtype(self) -> None:
        """dtype=str universal — no numeric coercion (ADR-004, RNF-03).

        Accepts both legacy ``object`` and pandas-3 ``StringDtype``; what
        matters is that no column was inferred as int/float.
        """
        result = self.parser.parse(CSV_FIXTURE)
        for col in result.dataframe.columns:
            assert pd.api.types.is_string_dtype(result.dataframe[col]), (
                f"Column '{col}' has dtype {result.dataframe[col].dtype}, expected string/object"
            )

    def test_leading_zero_sku_preserved_byte_by_byte(self) -> None:
        """SKU '03763BAR' must survive encoding and dtype=str (RNF-03)."""
        result = self.parser.parse(CSV_FIXTURE)
        # Find the column that contains SKU values (any column)
        sku_col = result.sku_column_hint
        assert sku_col is not None, "Parser must provide a sku_column_hint for the CSV fixture"
        skus = result.dataframe[sku_col].tolist()
        assert "03763BAR" in skus, "'03763BAR' not found — leading zeros were stripped"

    def test_detected_encoding_reported(self) -> None:
        result = self.parser.parse(CSV_FIXTURE)
        assert result.detected_encoding in {"utf-8", "utf-8-sig", "cp1252", "latin-1"}

    def test_synthetic_cp1252_csv(self, tmp_path: Path) -> None:
        """Encoding cascade: a cp1252-encoded CSV must be decoded correctly."""
        content = "sku,desc\nABC123,Ñoño\nDEF456,Año\n"
        cp1252_bytes = content.encode("cp1252")
        csv_file = tmp_path / "cp1252_test.csv"
        csv_file.write_bytes(cp1252_bytes)

        result = self.parser.parse(csv_file)
        assert len(result.dataframe) == 2
        assert "Ñoño" in result.dataframe["desc"].tolist()

    def test_list_sheets_returns_none_for_csv(self) -> None:
        sheets = self.parser.list_sheets(CSV_FIXTURE)
        assert sheets is None

    def test_unsupported_format_raises(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "not_a_csv.xyz"
        bad_file.write_text("data")
        with pytest.raises(UnsupportedFormatError):
            self.parser.parse(bad_file)


# ---------------------------------------------------------------------------
# T-3.3 — ExcelParser
# ---------------------------------------------------------------------------
class TestExcelParserXlsx:
    def setup_method(self) -> None:
        self.parser = ExcelParser()

    def test_fixture_row_count(self) -> None:
        """The occ_top_sales fixture must have exactly 1 232 data rows (T-1.2)."""
        result = self.parser.parse(XLSX_FIXTURE)
        assert len(result.dataframe) == 1232

    def test_all_columns_are_str_dtype(self) -> None:
        result = self.parser.parse(XLSX_FIXTURE)
        for col in result.dataframe.columns:
            assert pd.api.types.is_string_dtype(result.dataframe[col]), (
                f"Column '{col}' has dtype {result.dataframe[col].dtype}, expected string/object"
            )

    def test_unnamed_column_present(self) -> None:
        """The XLSX has a column D with no header name — must appear as-is (EB-06)."""
        result = self.parser.parse(XLSX_FIXTURE)
        cols = list(result.dataframe.columns)
        # pandas names unnamed columns "(sin nombre)" or "Unnamed: N"
        unnamed = [
            c for c in cols
            if "sin nombre" in str(c).lower()
            or "unnamed" in str(c).lower()
            or str(c).strip() == ""
        ]
        assert unnamed, f"Expected an unnamed/sin-nombre column, got: {cols}"

    def test_hash_na_values_preserved_as_string(self) -> None:
        """#N/A cells must arrive as the string '#N/A', not as NaN (ADR-004)."""
        result = self.parser.parse(XLSX_FIXTURE)
        flat = result.dataframe.to_numpy(dtype=object).flatten()
        # At least one cell should be '#N/A' (column D)
        na_strings = [v for v in flat if v == "#N/A"]
        assert na_strings, "#N/A not found as string — may have been converted to NaN"

    def test_list_sheets_xlsx(self) -> None:
        sheets = self.parser.list_sheets(XLSX_FIXTURE)
        assert sheets is not None
        assert "Hoja1" in sheets


class TestExcelParserXlsm:
    def setup_method(self) -> None:
        self.parser = ExcelParser()

    def test_xlsm_lists_eight_sheets(self) -> None:
        """The Amazon report fixture has exactly 8 sheets (T-1.2, T-3.3 DoD)."""
        sheets = self.parser.list_sheets(XLSM_FIXTURE)
        assert sheets is not None
        assert len(sheets) == 8, f"Expected 8 sheets, got {len(sheets)}: {sheets}"

    def test_xlsm_parse_does_not_execute_macros(self) -> None:
        """Parsing an xlsm must never evaluate VBA — read_only mode (EB-06)."""
        # If macros were executed we'd get an exception or side-effect.
        # Simply parsing without error is the assertion.
        result = self.parser.parse(XLSM_FIXTURE)
        assert result.dataframe is not None

    def test_xlsm_sheet_selection(self) -> None:
        """Parser must accept a sheet_name kwarg for multi-sheet files."""
        sheets = self.parser.list_sheets(XLSM_FIXTURE)
        assert sheets is not None
        first_sheet = sheets[0]
        result = self.parser.parse(XLSM_FIXTURE, sheet_name=first_sheet)
        assert result.dataframe is not None
