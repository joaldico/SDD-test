"""T-5.5 — Unit tests for header fingerprint computation (RF-12).

TDD: written BEFORE implementation.
"""

from __future__ import annotations

from marketplace_conciliator.ingestion.header_fingerprint import compute_header_fingerprint


class TestHeaderFingerprint:
    def test_same_headers_produce_same_fingerprint(self) -> None:
        headers = ["SKU", "Stock", "Precio"]
        assert compute_header_fingerprint(headers) == compute_header_fingerprint(headers)

    def test_different_order_produces_different_fingerprint(self) -> None:
        a = compute_header_fingerprint(["SKU", "Stock"])
        b = compute_header_fingerprint(["Stock", "SKU"])
        assert a != b

    def test_whitespace_is_normalized(self) -> None:
        a = compute_header_fingerprint([" SKU ", "Stock"])
        b = compute_header_fingerprint(["SKU", "Stock"])
        assert a == b

    def test_returns_64_char_hex_sha256(self) -> None:
        fp = compute_header_fingerprint(["A", "B"])
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)
