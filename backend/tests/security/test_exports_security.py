"""Export Security Tests — TASK 22.

Verifies:
- Neutralization of CSV / spreadsheet formula injection (DDE attacks)
- Safe handling of benign cells
- Export filename path traversal and CRLF prevention
- Filename bounding
"""

import pytest

from app.security.exceptions import ExportSecurityError
from app.security.export_security import sanitize_csv_cell, sanitize_export_filename


@pytest.mark.parametrize(
    "malicious_formula,expected_prefixed",
    [
        ("=cmd|'/c calc'!A1", "'=cmd|'/c calc'!A1"),
        ("+12345", "'+12345"),
        ("-1000", "'-1000"),
        ("@SUM(A1:A10)", "'@SUM(A1:A10)"),
        ("\tDDE_PAYLOAD", "'\tDDE_PAYLOAD"),
        ("\rFORMULA", "'\rFORMULA"),
    ],
)
def test_csv_formula_injection_prefixed(
    malicious_formula: str,
    expected_prefixed: str,
) -> None:
    sanitized = sanitize_csv_cell(malicious_formula)
    assert sanitized == expected_prefixed
    assert sanitized.startswith("'")


def test_csv_benign_values_preserved() -> None:
    assert sanitize_csv_cell("Revenue") == "Revenue"
    assert sanitize_csv_cell(450000) == "450000"
    assert sanitize_csv_cell("Total Profit: $120,000") == "Total Profit: $120,000"
    assert sanitize_csv_cell("") == ""
    assert sanitize_csv_cell(None) == ""


@pytest.mark.parametrize(
    "dangerous_filename",
    [
        "../../etc/passwd.csv",
        "..\\..\\windows\\system32.xlsx",
        "export\r\nSet-Cookie: session=evil.csv",
        "%2e%2e/secret.csv",
    ],
)
def test_export_filename_path_traversal_rejected(dangerous_filename: str) -> None:
    with pytest.raises(ExportSecurityError):
        sanitize_export_filename(dangerous_filename)


def test_export_filename_sanitized_and_bounded() -> None:
    raw = "My Monthly Report (Draft #1) 2026.csv"
    sanitized = sanitize_export_filename(raw, max_length=20)
    assert ".." not in sanitized
    assert len(sanitized) <= 20
    assert sanitized.endswith(".csv")
