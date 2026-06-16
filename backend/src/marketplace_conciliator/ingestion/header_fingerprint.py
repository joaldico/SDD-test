"""Header fingerprint for remembered column mappings (RF-12, T-5.5).

Computes a stable SHA-256 digest from the ordered list of column header names
detected during preview. Same header layout ⇒ same fingerprint ⇒ previous
confirmed mappings can be offered as defaults (OBJ-03 still requires human gate).
"""

from __future__ import annotations

import hashlib


def compute_header_fingerprint(header_names: list[str]) -> str:
    """Return a hex SHA-256 fingerprint for an ordered header list.

    Normalisation: strip surrounding whitespace on each name; order is preserved
    because ``column_index`` mappings are position-based.
    """
    normalised = [name.strip() for name in header_names]
    payload = "\x1f".join(normalised).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
