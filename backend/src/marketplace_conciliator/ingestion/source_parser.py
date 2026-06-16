"""SourceParser port -- ADR-004 / hexagonal boundary for file ingestion.

This module defines the output contract (``ParsedSource``) and the structural
protocol (``SourceParser``) that all concrete parser adapters must satisfy.
No I/O is performed here; this is pure domain vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class UnsupportedFormatError(ValueError):
    """Raised when a parser receives a file extension it cannot handle."""


class UnsupportedEncodingError(ValueError):
    """Raised when no encoding in the cascade can decode the file."""


# ---------------------------------------------------------------------------
# Output value object
# ---------------------------------------------------------------------------


@dataclass
class ParsedSource:
    """Result of parsing a single source file.

    Attributes:
        dataframe:         Parsed data -- ALL columns are ``object`` (str) dtype.
        sheet_name:        Sheet that was parsed; ``None`` for flat files.
        detected_encoding: Encoding used to decode the file; ``None`` for binary.
        sku_column_hint:   Best-guess column name containing SKU values, if any.
        warnings:          Non-fatal issues discovered during parsing.

    """

    dataframe: pd.DataFrame
    sheet_name: str | None = None
    detected_encoding: str | None = None
    sku_column_hint: str | None = None
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Port (structural Protocol -- ADR-001/004)
# ---------------------------------------------------------------------------


@runtime_checkable
class SourceParser(Protocol):
    """Structural protocol for all source-file parser adapters.

    Adapters must implement:
        ``parse(path, **kwargs) -> ParsedSource``
        ``list_sheets(path) -> list[str] | None``
    """

    def parse(self, path: Path, **kwargs: object) -> ParsedSource:
        """Parse ``path`` and return a :class:`ParsedSource`.

        Args:
            path:     Absolute path to the source file.
            **kwargs: Adapter-specific options (e.g. ``sheet_name``).

        Raises:
            UnsupportedFormatError: File extension not handled by this adapter.
            UnsupportedEncodingError: Could not decode the file with any
                encoding in the configured cascade.

        """
        ...

    def list_sheets(self, path: Path) -> list[str] | None:
        """Return the list of sheet names in ``path``, or ``None`` for flat files.

        Args:
            path: Absolute path to the source file.

        """
        ...
