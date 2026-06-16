"""T-5.2 — Unit tests for reporting.families (pure domain logic, TDD)."""

from __future__ import annotations

from marketplace_conciliator.reporting.families import (
    ErrorCodeBreakdown,
    RawFamilyRow,
    build_families_report,
)


class TestBuildFamiliesReport:
    def test_aggregates_codes_under_family_sorted_by_error_count(self) -> None:
        rows = [
            RawFamilyRow(
                family_code="AUTORIZACION_MARCA",
                display_name="Autorización de marca",
                sort_order=1,
                error_code="18299",
                message="Marca no autorizada",
                error_count=1786,
                family_unique_skus=950,
            ),
            RawFamilyRow(
                family_code="AUTORIZACION_MARCA",
                display_name="Autorización de marca",
                sort_order=1,
                error_code="18749",
                message="Uso indebido de marca",
                error_count=118,
                family_unique_skus=950,
            ),
        ]

        report = build_families_report(run_id=7, rows=rows)

        assert report.run_id == 7
        assert len(report.families) == 1
        family = report.families[0]
        assert family.code == "AUTORIZACION_MARCA"
        assert family.display_name == "Autorización de marca"
        assert family.total_errors == 1904
        assert family.unique_skus == 950
        assert family.codes == [
            ErrorCodeBreakdown(code="18299", message="Marca no autorizada", count=1786),
            ErrorCodeBreakdown(code="18749", message="Uso indebido de marca", count=118),
        ]
        assert report.sin_clasificar_warning is False

    def test_excludes_families_with_no_rows(self) -> None:
        report = build_families_report(run_id=1, rows=[])
        assert report.families == []
        assert report.sin_clasificar_warning is False

    def test_sin_clasificar_warning_when_family_has_content(self) -> None:
        rows = [
            RawFamilyRow(
                family_code="SIN_CLASIFICAR",
                display_name="Sin clasificar",
                sort_order=99,
                error_code="99999",
                message="Código desconocido",
                error_count=3,
                family_unique_skus=2,
            ),
        ]

        report = build_families_report(run_id=2, rows=rows)

        assert len(report.families) == 1
        assert report.families[0].code == "SIN_CLASIFICAR"
        assert report.sin_clasificar_warning is True

    def test_families_ordered_by_sort_order(self) -> None:
        rows = [
            RawFamilyRow(
                family_code="IMAGENES",
                display_name="Imágenes",
                sort_order=6,
                error_code="18320",
                message="Sin imagen",
                error_count=5,
                family_unique_skus=5,
            ),
            RawFamilyRow(
                family_code="AUTORIZACION_MARCA",
                display_name="Autorización de marca",
                sort_order=1,
                error_code="18299",
                message="Marca",
                error_count=10,
                family_unique_skus=8,
            ),
        ]

        report = build_families_report(run_id=3, rows=rows)

        assert [f.code for f in report.families] == [
            "AUTORIZACION_MARCA",
            "IMAGENES",
        ]
