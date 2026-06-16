"""CsvParser -- SourceParser adapter for CSV/TXT files (T-3.2 / ADR-004).

Implements:
  - Encoding cascade: UTF-8 -> cp1252 -> latin-1  (with BOM detection)
  - Delimiter sniffing via :func:`csv.Sniffer`
  - ``dtype=str`` universal -- no numeric coercion whatsoever (RNF-03)
  - SKU column hinting based on column name heuristics
"""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

import pandas as pd

from marketplace_conciliator.ingestion.source_parser import (
    ParsedSource,
    UnsupportedEncodingError,
    UnsupportedFormatError,
)

if TYPE_CHECKING:
    from pathlib import Path

_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".csv", ".txt", ".tsv"})

# Ordered encoding cascade (spec T-3.2)
_ENCODING_CASCADE: tuple[str, ...] = ("utf-8-sig", "utf-8", "cp1252", "latin-1")

# Canonical SKU column name patterns (case-insensitive fragments)
_SKU_HINTS: tuple[str, ...] = ("sku", "asin", "item_id", "product_id", "cod", "codigo")

# Number of bytes to hand to the sniffer
_SNIFF_BYTES = 8192


def _sniff_delimiter(raw_bytes: bytes, encoding: str) -> str:
    """Return the detected CSV delimiter, defaulting to ','."""
    try:
        sample = raw_bytes[:_SNIFF_BYTES].decode(encoding, errors="replace")
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return ","
    else:
        return dialect.delimiter


def _guess_sku_column(columns: list[str]) -> str | None:
    """Return the first column whose name matches a SKU hint pattern."""
    for col in columns:
        lower = col.lower()
        if any(hint in lower for hint in _SKU_HINTS):
            return col
    return None


class CsvParser:
    """Concrete CSV/TXT source-file parser (adapter for the SourceParser port)."""

    def parse(self, path: Path, **kwargs: object) -> ParsedSource:  # noqa: ARG002
        """Parse a CSV/TXT file into a :class:`ParsedSource`.

        Args:
            path:     Absolute path to the CSV or TXT file.
            **kwargs: Accepted but ignored (interface compatibility).

        Raises:
            UnsupportedFormatError:   File extension is not in the supported set.
            UnsupportedEncodingError: None of the encoding cascade candidates
                could decode the file without errors.

        """
        if path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            msg = (
                f"CsvParser does not handle '{path.suffix}' files. "
                f"Supported: {sorted(_SUPPORTED_EXTENSIONS)}"
            )
            raise UnsupportedFormatError(msg)

        raw_bytes = path.read_bytes()

        # Try each encoding in cascade order
        used_encoding: str | None = None
        for enc in _ENCODING_CASCADE:
            try:
                raw_bytes.decode(enc, errors="strict")
                used_encoding = enc
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if used_encoding is None:
            msg = f"Could not decode '{path.name}' with any of {_ENCODING_CASCADE}."
            raise UnsupportedEncodingError(msg)

        delimiter = _sniff_delimiter(raw_bytes, used_encoding)

        df = pd.read_csv(
            io.BytesIO(raw_bytes),
            sep=delimiter,
            dtype=str,
            encoding=used_encoding,
            keep_default_na=False,
            na_filter=False,
        )

        # Normalise the canonical encoding name for reporting
        reported_enc = used_encoding.replace("utf-8-sig", "utf-8")

        sku_hint = _guess_sku_column(list(df.columns))

        return ParsedSource(
            dataframe=df,
            sheet_name=None,
            detected_encoding=reported_enc,
            sku_column_hint=sku_hint,
        )

    def list_sheets(self, path: Path) -> list[str] | None:  # noqa: ARG002
        """CSV files are flat -- always returns ``None``."""
        return None
