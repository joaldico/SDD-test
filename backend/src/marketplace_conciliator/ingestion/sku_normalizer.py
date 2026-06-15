"""SKU normalisation — RN-01 through RN-06 (spec 2.5).

This module is a pure-function layer with zero I/O side effects.  It may be
called from parsers, reconciliation stages, or anywhere else without
introducing cross-module coupling (ADR-001).
"""

from __future__ import annotations

from dataclasses import dataclass

# Excel / spreadsheet sentinel error strings that must be treated as invalid.
_EXCEL_ERRORS: frozenset[str] = frozenset(
    {"#N/A", "#REF!", "#VALUE!", "#NAME?", "#NULL!", "#DIV/0!", "#NUM!", "#ERROR!"},
)


@dataclass(frozen=True)
class NormalisationResult:
    """Immutable result of a single SKU normalisation attempt.

    Attributes:
        original: The raw string that was passed to ``normalise_sku``.
        value:    The normalised SKU string, or ``None`` when invalid.
        is_valid: ``True`` iff ``value`` is not ``None``.

    """

    original: str | None
    value: str | None
    is_valid: bool


def normalise_sku(raw: str | None) -> NormalisationResult:
    """Normalise a raw SKU string according to RN-01..RN-06.

    Rules applied in order:
        RN-01  Strip leading/trailing ASCII whitespace.
        RN-02  Strip NBSP (U+00A0) from both ends (treated as whitespace).
        RN-03  Convert to uppercase.
        RN-04  Preserve leading zeros — no numeric coercion whatsoever.
        RN-05  Preserve dots and other non-whitespace characters verbatim.
        RN-06  Return an invalid result for blank values and Excel sentinels.

    Args:
        raw: The raw value from the source file.  May be ``None`` when the
             upstream parser converts ``NaN`` cells to Python ``None``.

    Returns:
        A :class:`NormalisationResult` with ``is_valid=False`` when the input
        is blank, ``None``, or an Excel error sentinel.

    """
    if raw is None:
        return NormalisationResult(original=None, value=None, is_valid=False)

    # RN-01/RN-02: strip ASCII whitespace AND NBSP from both ends.
    stripped = raw.strip(" \t\n\r\f\v\u00a0")

    # RN-06: reject empty-after-strip
    if not stripped:
        return NormalisationResult(original=raw, value=None, is_valid=False)

    # RN-06: reject Excel formula error sentinels
    if stripped in _EXCEL_ERRORS:
        return NormalisationResult(original=raw, value=None, is_valid=False)

    # RN-03: uppercase; RN-04: no numeric casting; RN-05: dots/other chars untouched.
    normalised = stripped.upper()

    return NormalisationResult(original=raw, value=normalised, is_valid=True)
