"""TQ-8: every defect in docs/tests/defect-log.md names a regression test that exists."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "docs" / "tests" / "defect-log.md"
TEST_REF = re.compile(r"`(tests/[\w/]+\.py)::(\w+)`")


def defect_rows() -> list[list[str]]:
    rows = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        if re.match(r"\|\s*D-\d{3}\s*\|", line):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


def test_defect_log_has_entries_with_all_columns() -> None:
    rows = defect_rows()
    assert rows, "defect log is empty"
    ids = [r[0] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate defect IDs"
    for row in rows:
        assert len(row) == 8 and all(row), f"incomplete defect row {row[0]}"


def test_every_defect_has_an_existing_regression_test() -> None:
    for row in defect_rows():
        refs = TEST_REF.findall(row[7])
        assert refs, f"{row[0]} has no regression test reference"
        for path, name in refs:
            source = (ROOT / path).read_text(encoding="utf-8")
            assert re.search(rf"^(async )?def {name}\(", source, re.M), f"{row[0]}: {path}::{name} not found"
