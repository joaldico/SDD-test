"""T-3.4 — Tests for BlockLocator (TDD: written before implementation).

Spec references: EB-02 (block title), EB-03 (fallback when missing), EB-04 (example row).
DoD: bloque hallado en fila 572; SKU en última columna; ABC123 descartada y contada;
     sin título → BlockNotFoundError; doble cabecera de Plantilla manejada.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from marketplace_conciliator.ingestion.block_locator import (
    BlockLocator,
    BlockNotFoundError,
    LocatedBlock,
)
from marketplace_conciliator.ingestion.excel_parser import ExcelParser

FIXTURES = Path(__file__).parent / "fixtures"
XLSM_FIXTURE = FIXTURES / "amazon_processing_summary_anonymized.xlsm"
RESUMEN_SHEET = "Resumen de procesamiento"
PLANTILLA_SHEET = "Plantilla"


@pytest.fixture(scope="module")
def resumen_df() -> pd.DataFrame:
    """Full 'Resumen de procesamiento' sheet as a DataFrame of strings."""
    parser = ExcelParser()
    return parser.parse(XLSM_FIXTURE, sheet_name=RESUMEN_SHEET).dataframe


@pytest.fixture(scope="module")
def plantilla_df() -> pd.DataFrame:
    """Full 'Plantilla' sheet as a DataFrame of strings."""
    parser = ExcelParser()
    return parser.parse(XLSM_FIXTURE, sheet_name=PLANTILLA_SHEET).dataframe


class TestLocateErrorsBlock:
    def setup_method(self) -> None:
        self.locator = BlockLocator()

    def test_block_located_and_is_located_block(self, resumen_df: pd.DataFrame) -> None:
        block = self.locator.locate_errors_block(resumen_df)
        assert isinstance(block, LocatedBlock)

    def test_data_starts_at_sheet_row_572(self, resumen_df: pd.DataFrame) -> None:
        """First data row must be at 1-indexed sheet row 572 (EB-02, DoD T-3.4)."""
        block = self.locator.locate_errors_block(resumen_df)
        assert block.data_start_row == 572

    def test_sku_column_is_last_column(self, resumen_df: pd.DataFrame) -> None:
        """SKU column must be the rightmost column in the block (DoD T-3.4)."""
        block = self.locator.locate_errors_block(resumen_df)
        assert block.sku_column is not None
        cols = list(block.dataframe.columns)
        assert block.sku_column == cols[-1], (
            f"SKU column '{block.sku_column}' is not last; columns are {cols}"
        )

    def test_dataframe_columns_match_header_row(self, resumen_df: pd.DataFrame) -> None:
        """Block DataFrame columns come from the header row immediately after the title."""
        block = self.locator.locate_errors_block(resumen_df)
        # The real header has '#', 'Código de error', etc. as column names
        assert "#" in block.dataframe.columns
        assert "SKU" in block.dataframe.columns

    def test_dataframe_contains_real_sku_values(self, resumen_df: pd.DataFrame) -> None:
        """After locating, data rows must contain actual SKU strings, not None."""
        block = self.locator.locate_errors_block(resumen_df)
        skus = block.dataframe[block.sku_column].tolist()
        non_empty = [s for s in skus if s and str(s).strip()]
        assert non_empty, "No SKU values found in located block"

    def test_title_row_attribute(self, resumen_df: pd.DataFrame) -> None:
        """title_row should be the 1-indexed sheet row containing the block title."""
        block = self.locator.locate_errors_block(resumen_df)
        assert block.title_row == 570

    def test_no_title_raises_block_not_found_error(self) -> None:
        """EB-03: when the block title is absent, raise BlockNotFoundError."""
        df = pd.DataFrame({"col1": ["a", "b"], "col2": ["c", "d"]})
        with pytest.raises(BlockNotFoundError, match="Errores y advertencias por SKU"):
            BlockLocator().locate_errors_block(df)


class TestParsePlantillaBlock:
    def setup_method(self) -> None:
        self.locator = BlockLocator()

    def test_parse_returns_located_block(self, plantilla_df: pd.DataFrame) -> None:
        block = self.locator.parse_plantilla(plantilla_df)
        assert isinstance(block, LocatedBlock)

    def test_abc123_not_in_sku_column(self, plantilla_df: pd.DataFrame) -> None:
        """EB-04: Amazon example row (ABC123) must be discarded."""
        block = self.locator.parse_plantilla(plantilla_df)
        assert block.sku_column is not None
        skus = block.dataframe[block.sku_column].tolist()
        assert "ABC123" not in skus, "ABC123 example row was NOT discarded"

    def test_discarded_rows_counted(self, plantilla_df: pd.DataFrame) -> None:
        """The example row must be accounted in discarded_rows."""
        block = self.locator.parse_plantilla(plantilla_df)
        assert block.discarded_rows >= 1

    def test_sku_column_is_sku(self, plantilla_df: pd.DataFrame) -> None:
        """The SKU column in Plantilla uses the human-readable label 'SKU'."""
        block = self.locator.parse_plantilla(plantilla_df)
        assert block.sku_column == "SKU"

    def test_data_rows_contain_real_skus(self, plantilla_df: pd.DataFrame) -> None:
        """After discarding example rows, actual SKU values (TWA85XL, K2.65…) survive."""
        block = self.locator.parse_plantilla(plantilla_df)
        skus = set(block.dataframe[block.sku_column].tolist())
        assert "TWA85XL" in skus or any(s.startswith("SKU0") for s in skus), (
            f"Expected real SKU values, got sample: {list(skus)[:5]}"
        )

    def test_double_header_uses_human_readable_labels(self, plantilla_df: pd.DataFrame) -> None:
        """Columns come from the human-readable label row (row 4), not the technical row."""
        block = self.locator.parse_plantilla(plantilla_df)
        # Human-readable labels include 'Submission Status' and 'SKU'
        cols = list(block.dataframe.columns)
        assert "SKU" in cols
        # Technical names like 'contribution_sku#1.value' should NOT be column names
        technical = [c for c in cols if "#" in c and "." in c]
        assert not technical, f"Technical attribute names found in columns: {technical}"
