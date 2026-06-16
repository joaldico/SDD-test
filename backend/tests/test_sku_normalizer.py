"""T-3.1 — Tests for SKU normalisation (RN-01..RN-06 from spec 2.5).

All tests are table-driven and written BEFORE the implementation (TDD red→green).
"""

from __future__ import annotations

import pytest

from marketplace_conciliator.ingestion.sku_normalizer import normalise_sku


# ---------------------------------------------------------------------------
# Happy-path table: (raw_input, expected_normalised)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # RN-01: leading/trailing whitespace stripped
        ("  TWA85XL  ", "TWA85XL"),
        # RN-02: NBSP (U+00A0) treated as whitespace and stripped
        (" twa85xl\u00a0", "TWA85XL"),
        # RN-02: mixed NBSP + regular spaces
        ("\u00a0 twa85xl \u00a0", "TWA85XL"),
        # RN-03: uppercase normalisation
        ("twa85xl", "TWA85XL"),
        ("Twa85Xl", "TWA85XL"),
        # RN-04: leading zeros MUST be preserved (numeric-looking strings)
        ("03763BAR", "03763BAR"),
        ("03763BBS", "03763BBS"),
        ("03763BNR", "03763BNR"),
        ("03763BRS", "03763BRS"),
        # RN-05: decimal-looking string treated as text, preserved exactly
        ("K2.65", "K2.65"),
        # RN-05: dots preserved when part of the SKU
        ("AB.12.CD", "AB.12.CD"),
        # RN-06: already-normalised passes through unchanged
        ("SKU001", "SKU001"),
        # Internal whitespace collapsed to nothing (not split into tokens)
        ("AB  CD", "AB  CD"),  # internal spaces preserved (only strip outer)
    ],
)
def test_normalise_happy(raw: str, expected: str) -> None:
    result = normalise_sku(raw)
    assert result.value == expected
    assert result.is_valid is True
    assert result.original == raw


# ---------------------------------------------------------------------------
# Invalid / sentinel values — RN-06 in spec 2.5
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw",
    [
        "#N/A",
        "#REF!",
        "#VALUE!",
        "#NAME?",
        "#NULL!",
        "#DIV/0!",
        "#NUM!",
        "",         # blank string
        "   ",      # whitespace-only
        "\u00a0",  # NBSP-only
    ],
)
def test_normalise_invalid(raw: str) -> None:
    result = normalise_sku(raw)
    assert result.is_valid is False
    assert result.value is None
    assert result.original == raw


# ---------------------------------------------------------------------------
# None input (can arrive from pandas NaN-as-None conversion)
# ---------------------------------------------------------------------------
def test_normalise_none() -> None:
    result = normalise_sku(None)
    assert result.is_valid is False
    assert result.value is None


# ---------------------------------------------------------------------------
# Result dataclass API contract
# ---------------------------------------------------------------------------
def test_result_is_hashable() -> None:
    """NormalisationResult must be usable as a dict key (frozen dataclass)."""
    r = normalise_sku("SKU001")
    _ = {r: True}


def test_result_fields() -> None:
    r = normalise_sku(" twa85xl\u00a0")
    assert r.value == "TWA85XL"
    assert r.original == " twa85xl\u00a0"
    assert r.is_valid is True
