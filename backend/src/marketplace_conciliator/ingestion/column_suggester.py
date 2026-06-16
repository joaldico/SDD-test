"""ColumnSuggester -- heuristic column mapping for SKU and Stock fields (T-3.5).

Design principles (OBJ-03, plan 3.7):
  - Returns *suggestions* only — never confirms a mapping autonomously.
  - Every suggestion carries a ``reason`` string explaining the evidence.
  - Confidence is a float in [0.0, 1.0]; higher means stronger evidence.
  - Two scoring layers:
      1. Name-based: exact or partial match of column name against known
         synonyms for each logical field.
      2. Profile-based: analysis of cell values (uniqueness ratio, numeric
         pattern) adds or adjusts confidence.
  - The top suggestion per logical field is returned if confidence > 0.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


# ---------------------------------------------------------------------------
# Domain vocabulary
# ---------------------------------------------------------------------------


class LogicalField(StrEnum):
    """Logical fields that require a column mapping."""

    SKU = "sku"
    STOCK = "stock"


# Name fragments used for matching — ordered by specificity (most specific first)
_SKU_NAME_HINTS: tuple[tuple[str, float], ...] = (
    ("sku", 0.95),
    ("asin", 0.90),
    ("item_id", 0.85),
    ("product_id", 0.80),
    ("cod", 0.70),
    ("codigo", 0.70),
    ("reference", 0.65),
    ("ref", 0.60),
)

_STOCK_NAME_HINTS: tuple[tuple[str, float], ...] = (
    ("stock", 0.95),
    ("qty", 0.85),
    ("quantity", 0.85),
    ("cantidad", 0.85),
    ("units", 0.80),
    ("inventory", 0.75),
    ("existencias", 0.75),
    ("disponible", 0.70),
)

# Minimum uniqueness ratio to consider a column a candidate SKU (most SKUs are unique)
_SKU_MIN_UNIQUENESS: float = 0.80
_SKU_UNIQUENESS_BONUS: float = 0.10

# Fraction of values that must be numeric-looking to boost stock confidence
_STOCK_NUMERIC_THRESHOLD: float = 0.70
_STOCK_NUMERIC_BONUS: float = 0.10

# Minimum confidence to include a suggestion in the output
_MIN_CONFIDENCE: float = 0.30


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ColumnSuggestion:
    """A single column suggestion for a logical field.

    Attributes:
        logical_field:  The semantic role this column is suggested for.
        column_name:    Name of the suggested column in the source DataFrame.
        column_index:   Zero-based position of the column in the DataFrame.
        confidence:     Score in [0.0, 1.0] indicating suggestion strength.
        reason:         Human-readable explanation of why this column was
                        selected (MUST always be present when confidence > 0).

    """

    logical_field: LogicalField
    column_name: str
    column_index: int
    confidence: float
    reason: str

    def __post_init__(self) -> None:  # noqa: D105
        if not (0.0 <= self.confidence <= 1.0):
            msg = f"confidence must be in [0, 1], got {self.confidence}"
            raise ValueError(msg)
        if self.confidence > 0 and not self.reason:
            msg = "reason must not be empty when confidence > 0"
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# ColumnSuggester
# ---------------------------------------------------------------------------


class ColumnSuggester:
    """Heuristic engine that suggests column mappings without confirming them.

    Usage::

        suggester = ColumnSuggester()
        suggestions = suggester.suggest(dataframe)
        for s in suggestions:
            print(s.logical_field, s.column_name, s.confidence, s.reason)
    """

    def suggest(self, df: pd.DataFrame) -> list[ColumnSuggestion]:
        """Return suggestions for SKU and Stock columns in ``df``.

        Only suggestions with confidence >= ``_MIN_CONFIDENCE`` are returned.
        The caller must confirm any mapping before it is persisted (OBJ-03).

        Args:
            df: DataFrame with object-dtype columns (all values are strings).

        Returns:
            List of :class:`ColumnSuggestion` sorted by (logical_field, -confidence).

        """
        columns = list(df.columns)
        suggestions: list[ColumnSuggestion] = []

        for idx, col in enumerate(columns):
            col_lower = str(col).lower().strip()

            # --- SKU candidate ---
            sku_conf, sku_reason = _score_name(col_lower, _SKU_NAME_HINTS)
            if sku_conf >= _MIN_CONFIDENCE:
                profile_bonus, profile_reason = _profile_sku(df, col)
                total_conf = min(1.0, sku_conf + profile_bonus)
                reason_parts = [sku_reason]
                if profile_reason:
                    reason_parts.append(profile_reason)
                suggestions.append(
                    ColumnSuggestion(
                        logical_field=LogicalField.SKU,
                        column_name=col,
                        column_index=idx,
                        confidence=total_conf,
                        reason="; ".join(reason_parts),
                    ),
                )

            # --- Stock candidate ---
            stock_conf, stock_reason = _score_name(col_lower, _STOCK_NAME_HINTS)
            if stock_conf >= _MIN_CONFIDENCE:
                profile_bonus, profile_reason = _profile_stock(df, col)
                total_conf = min(1.0, stock_conf + profile_bonus)
                reason_parts = [stock_reason]
                if profile_reason:
                    reason_parts.append(profile_reason)
                suggestions.append(
                    ColumnSuggestion(
                        logical_field=LogicalField.STOCK,
                        column_name=col,
                        column_index=idx,
                        confidence=total_conf,
                        reason="; ".join(reason_parts),
                    ),
                )

        suggestions.sort(key=lambda s: (s.logical_field.value, -s.confidence))
        return suggestions


# ---------------------------------------------------------------------------
# Private scoring helpers
# ---------------------------------------------------------------------------


def _score_name(
    col_lower: str,
    hints: tuple[tuple[str, float], ...],
) -> tuple[float, str]:
    """Return (confidence, reason) based on name-pattern matching."""
    for hint, base_conf in hints:
        hint_lower = hint.lower()
        if col_lower == hint_lower:
            return base_conf, f"column name exactly matches '{hint}'"
        if col_lower.startswith(hint_lower):
            return base_conf - 0.05, f"column name starts with '{hint}'"
        if hint_lower in col_lower:
            return base_conf - 0.10, f"column name contains '{hint}'"
    return 0.0, ""


def _profile_sku(df: pd.DataFrame, col: str) -> tuple[float, str]:
    """Compute a uniqueness-based bonus for SKU candidate columns."""
    try:
        series = df[col].dropna().astype(str)
        if len(series) == 0:
            return 0.0, ""
        uniqueness = series.nunique() / len(series)
        if uniqueness >= _SKU_MIN_UNIQUENESS:
            return (
                _SKU_UNIQUENESS_BONUS,
                f"high value uniqueness ({uniqueness:.0%} of values are distinct)",
            )
    except Exception:  # noqa: BLE001, S110
        pass
    return 0.0, ""


# Pre-compiled pattern: matches integers and decimals (optional leading sign)
_NUMERIC_RE: re.Pattern[str] = re.compile(r"^[+-]?\d+([.,]\d+)?$")


def _profile_stock(df: pd.DataFrame, col: str) -> tuple[float, str]:
    """Compute a numeric-pattern bonus for Stock candidate columns."""
    try:
        series = df[col].dropna().astype(str)
        series = series[series.str.strip() != ""]
        if len(series) == 0:
            return 0.0, ""
        numeric_count = series.apply(lambda v: bool(_NUMERIC_RE.match(v.strip()))).sum()
        ratio = numeric_count / len(series)
        if ratio >= _STOCK_NUMERIC_THRESHOLD:
            return (
                _STOCK_NUMERIC_BONUS,
                f"most values are numeric ({ratio:.0%} match integer/decimal pattern)",
            )
    except Exception:  # noqa: BLE001, S110
        pass
    return 0.0, ""
