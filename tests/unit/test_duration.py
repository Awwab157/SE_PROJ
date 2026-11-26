import pytest

from yt_intel_mcp.duration import format_duration, parse_duration


@pytest.mark.parametrize(
    ("value", "expected"),
    [("PT1H2M10S", 3730), ("PT45S", 45), ("PT10M", 600), ("PT2H", 7200), ("P1DT1S", 86401), ("pt3m5s", 185)],
)
def test_parse(value: str, expected: int) -> None:
    assert parse_duration(value) == expected


@pytest.mark.parametrize("value", [None, "", "P0D", "PT0S", "PT", "P", "garbage", "1:02:10", 42])
def test_unknown_is_none_never_zero(value) -> None:
    assert parse_duration(value) is None


def test_format() -> None:
    assert format_duration(3730) == "1h 02m 10s"
    assert format_duration(45) == "0m 45s"
    assert format_duration(None) == "unknown"
