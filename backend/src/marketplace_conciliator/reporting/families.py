"""Families report builder — pure domain logic (T-5.2).

Aggregates item_errors by business family and error code for Vista 1.
No I/O or framework imports (ADR-001 hexagonal boundary).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class _FamilyAccumulator:
    display_name: str
    sort_order: int
    family_unique_skus: int
    total_errors: int = 0
    codes: list[ErrorCodeBreakdown] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RawFamilyRow:
    """One grouped row from the families SQL query."""

    family_code: str
    display_name: str
    sort_order: int
    error_code: str
    message: str
    error_count: int
    family_unique_skus: int


@dataclass(frozen=True, slots=True)
class ErrorCodeBreakdown:
    """Drill-down entry for a single Amazon error code within a family."""

    code: str
    message: str
    count: int


@dataclass(frozen=True, slots=True)
class FamilyBreakdown:
    """Aggregated family with nested code breakdown (plan 3.7 Vista 1)."""

    code: str
    display_name: str
    unique_skus: int
    total_errors: int
    codes: list[ErrorCodeBreakdown]


@dataclass(frozen=True, slots=True)
class FamiliesReport:
    """Structured payload for GET /runs/{id}/report/families."""

    run_id: int
    families: list[FamilyBreakdown]
    sin_clasificar_warning: bool


def build_families_report(*, run_id: int, rows: list[RawFamilyRow]) -> FamiliesReport:
    """Build the families report from flat SQL aggregation rows."""
    if not rows:
        return FamiliesReport(
            run_id=run_id,
            families=[],
            sin_clasificar_warning=False,
        )

    grouped: dict[str, _FamilyAccumulator] = {}
    for row in rows:
        acc = grouped.setdefault(
            row.family_code,
            _FamilyAccumulator(
                display_name=row.display_name,
                sort_order=row.sort_order,
                family_unique_skus=row.family_unique_skus,
            ),
        )
        acc.total_errors += row.error_count
        acc.codes.append(
            ErrorCodeBreakdown(
                code=row.error_code,
                message=row.message,
                count=row.error_count,
            ),
        )

    families: list[FamilyBreakdown] = []
    for family_code, acc in grouped.items():
        acc.codes.sort(key=lambda c: c.count, reverse=True)
        families.append(
            FamilyBreakdown(
                code=family_code,
                display_name=acc.display_name,
                unique_skus=acc.family_unique_skus,
                total_errors=acc.total_errors,
                codes=acc.codes,
            ),
        )

    families.sort(key=lambda f: grouped[f.code].sort_order)

    sin_clasificar_warning = any(
        f.code == "SIN_CLASIFICAR" and f.total_errors > 0 for f in families
    )

    return FamiliesReport(
        run_id=run_id,
        families=families,
        sin_clasificar_warning=sin_clasificar_warning,
    )
