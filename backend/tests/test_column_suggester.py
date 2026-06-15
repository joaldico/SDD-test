"""T-3.5 — Tests for ColumnSuggester (TDD: written before implementation).

Spec references: OBJ-03, plan 3.7.
DoD: sugiere sku/stock correctos en los 3 fixtures; nunca devuelve confianza sin
     reason; la heurística NO confirma nada por sí sola.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from marketplace_conciliator.ingestion.block_locator import BlockLocator
from marketplace_conciliator.ingestion.column_suggester import (
    ColumnSuggester,
    ColumnSuggestion,
    LogicalField,
)
from marketplace_conciliator.ingestion.csv_parser import CsvParser
from marketplace_conciliator.ingestion.excel_parser import ExcelParser

FIXTURES = Path(__file__).parent / "fixtures"
CSV_FIXTURE = FIXTURES / "wavemarket_fullstock_anonymized.csv"
XLSX_FIXTURE = FIXTURES / "occ_top_sales_anonymized.xlsx"
XLSM_FIXTURE = FIXTURES / "amazon_processing_summary_anonymized.xlsm"


# ---------------------------------------------------------------------------
# Fixtures (pytest)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def csv_df() -> pd.DataFrame:
    return CsvParser().parse(CSV_FIXTURE).dataframe


@pytest.fixture(scope="module")
def xlsx_df() -> pd.DataFrame:
    return ExcelParser().parse(XLSX_FIXTURE).dataframe


@pytest.fixture(scope="module")
def xlsm_errors_df() -> pd.DataFrame:
    """Block DataFrame from the Amazon errors-per-SKU section."""
    parser = ExcelParser()
    resumen_df = parser.parse(XLSM_FIXTURE, sheet_name="Resumen de procesamiento").dataframe
    return BlockLocator().locate_errors_block(resumen_df).dataframe


# ---------------------------------------------------------------------------
# ColumnSuggestion value-object contract
# ---------------------------------------------------------------------------


class TestColumnSuggestionContract:
    def test_has_required_fields(self) -> None:
        s = ColumnSuggestion(
            logical_field=LogicalField.SKU,
            column_name="sku",
            column_index=0,
            confidence=0.9,
            reason="column name contains 'sku'",
        )
        assert s.logical_field == LogicalField.SKU
        assert s.column_name == "sku"
        assert s.column_index == 0
        assert 0.0 <= s.confidence <= 1.0
        assert s.reason

    def test_confidence_always_has_reason(self) -> None:
        """Every suggestion with confidence > 0 must have a non-empty reason."""
        s = ColumnSuggestion(
            logical_field=LogicalField.STOCK,
            column_name="stock",
            column_index=1,
            confidence=0.8,
            reason="column name contains 'stock'",
        )
        assert s.reason, "Suggestion has confidence but empty reason"

    def test_suggestion_does_not_confirm(self) -> None:
        """Suggestions never carry a 'confirmed' flag — confirmation is human-only."""
        s = ColumnSuggestion(
            logical_field=LogicalField.SKU,
            column_name="sku",
            column_index=0,
            confidence=1.0,
            reason="exact match",
        )
        assert not hasattr(s, "confirmed"), "ColumnSuggestion must not have 'confirmed' field"


# ---------------------------------------------------------------------------
# T-3.5 core heuristic tests
# ---------------------------------------------------------------------------


class TestColumnSuggesterOnCsvFixture:
    """CSV fixture: columns ['sku', 'stock', 'site', 'condition']."""

    def setup_method(self) -> None:
        self.suggester = ColumnSuggester()

    def test_suggests_sku_column(self, csv_df: pd.DataFrame) -> None:
        suggestions = self.suggester.suggest(csv_df)
        sku_sug = [s for s in suggestions if s.logical_field == LogicalField.SKU]
        assert sku_sug, "No SKU suggestion returned for CSV fixture"
        best = max(sku_sug, key=lambda s: s.confidence)
        assert best.column_name == "sku"

    def test_suggests_stock_column(self, csv_df: pd.DataFrame) -> None:
        suggestions = self.suggester.suggest(csv_df)
        stock_sug = [s for s in suggestions if s.logical_field == LogicalField.STOCK]
        assert stock_sug, "No STOCK suggestion returned for CSV fixture"
        best = max(stock_sug, key=lambda s: s.confidence)
        assert best.column_name == "stock"

    def test_every_suggestion_has_reason(self, csv_df: pd.DataFrame) -> None:
        for s in self.suggester.suggest(csv_df):
            assert s.reason, f"Suggestion {s} has confidence {s.confidence} but no reason"

    def test_confidence_in_valid_range(self, csv_df: pd.DataFrame) -> None:
        for s in self.suggester.suggest(csv_df):
            assert 0.0 <= s.confidence <= 1.0


class TestColumnSuggesterOnXlsxFixture:
    """XLSX fixture: columns ['Name', 'SKU', 'Supplier', '(sin nombre) 3', 'stock occ']."""

    def setup_method(self) -> None:
        self.suggester = ColumnSuggester()

    def test_suggests_sku_column(self, xlsx_df: pd.DataFrame) -> None:
        suggestions = self.suggester.suggest(xlsx_df)
        sku_sug = [s for s in suggestions if s.logical_field == LogicalField.SKU]
        assert sku_sug, "No SKU suggestion for XLSX fixture"
        best = max(sku_sug, key=lambda s: s.confidence)
        assert best.column_name == "SKU"

    def test_suggests_stock_column(self, xlsx_df: pd.DataFrame) -> None:
        suggestions = self.suggester.suggest(xlsx_df)
        stock_sug = [s for s in suggestions if s.logical_field == LogicalField.STOCK]
        assert stock_sug, "No STOCK suggestion for XLSX fixture"
        best = max(stock_sug, key=lambda s: s.confidence)
        assert best.column_name == "stock occ"

    def test_every_suggestion_has_reason(self, xlsx_df: pd.DataFrame) -> None:
        for s in self.suggester.suggest(xlsx_df):
            assert s.reason


class TestColumnSuggesterOnXlsmErrorsBlock:
    """XLSM fixture errors block: columns include 'SKU' (last), no stock column."""

    def setup_method(self) -> None:
        self.suggester = ColumnSuggester()

    def test_suggests_sku_column(self, xlsm_errors_df: pd.DataFrame) -> None:
        suggestions = self.suggester.suggest(xlsm_errors_df)
        sku_sug = [s for s in suggestions if s.logical_field == LogicalField.SKU]
        assert sku_sug, "No SKU suggestion for XLSM errors block"
        best = max(sku_sug, key=lambda s: s.confidence)
        assert best.column_name == "SKU"

    def test_every_suggestion_has_reason(self, xlsm_errors_df: pd.DataFrame) -> None:
        for s in self.suggester.suggest(xlsm_errors_df):
            assert s.reason


class TestColumnSuggesterEdgeCases:
    def test_no_suggestions_for_unrecognized_schema(self) -> None:
        """An empty/opaque DataFrame should return an empty list (no crash)."""
        df = pd.DataFrame({"col_a": ["x", "y"], "col_b": ["1", "2"]})
        suggestions = ColumnSuggester().suggest(df)
        # May return empty or low-confidence suggestions — must not raise
        for s in suggestions:
            assert s.reason

    def test_high_confidence_name_match_beats_profile(self) -> None:
        """Exact name match should yield confidence >= 0.85."""
        df = pd.DataFrame({"sku": ["ABC", "DEF"], "qty": ["10", "20"]})
        suggestions = ColumnSuggester().suggest(df)
        sku_sug = [s for s in suggestions if s.logical_field == LogicalField.SKU]
        assert sku_sug
        best = max(sku_sug, key=lambda s: s.confidence)
        assert best.confidence >= 0.85
