"""Lookup of previously confirmed mappings by header fingerprint (RF-12, T-5.5)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session  # noqa: TC002

from marketplace_conciliator.platform.db.models.runs import ColumnMapping


@dataclass(frozen=True, slots=True)
class RememberedMapping:
    """A logical field mapping recalled from a prior run."""

    column_index: int
    from_run_id: int
    reason: str


def lookup_remembered_mappings(
    db: Session,
    *,
    role: str,
    header_fingerprint: str,
    exclude_source_file_id: int,
) -> dict[str, RememberedMapping]:
    """Find the most recent confirmed mappings for the same role + header fingerprint.

    Returns an empty dict when no prior mapping exists. The caller merges the
    result into the preview response; confirmation is still required (OBJ-03).
    """
    source_file_id_row = db.execute(
        sa_text("""
            SELECT sf.id, sf.run_id
            FROM source_files sf
            WHERE sf.role = :role
              AND sf.header_fingerprint = :fingerprint
              AND sf.id != :exclude_id
              AND EXISTS (
                  SELECT 1 FROM column_mappings cm
                  WHERE cm.source_file_id = sf.id
              )
            ORDER BY (
                SELECT MAX(cm2.confirmed_at)
                FROM column_mappings cm2
                WHERE cm2.source_file_id = sf.id
            ) DESC
            LIMIT 1
        """),
        {
            "role": role,
            "fingerprint": header_fingerprint,
            "exclude_id": exclude_source_file_id,
        },
    ).fetchone()

    if source_file_id_row is None:
        return {}

    prior_file_id = int(source_file_id_row[0])
    from_run_id = int(source_file_id_row[1])

    mappings = (
        db.query(ColumnMapping)
        .filter(ColumnMapping.source_file_id == prior_file_id)
        .all()
    )

    return {
        cm.logical_field: RememberedMapping(
            column_index=cm.source_column_index,
            from_run_id=from_run_id,
            reason=(
                f"Mapeo confirmado en ejecución #{from_run_id} "
                f"(columna «{cm.source_column_name}»)"
            ),
        )
        for cm in mappings
    }
