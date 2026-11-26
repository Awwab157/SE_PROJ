"""ISO 8601 duration parsing (FR-4.5). Unknown durations are ``None``, never 0."""

from __future__ import annotations

import re

_DURATION_RE = re.compile(
    r"^P(?:(?P<weeks>\d+)W)?(?:(?P<days>\d+)D)?"
    r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$"
)


def parse_duration(value: str | None) -> int | None:
    """``PT1H2M10S`` -> 3730. Live streams (``P0D``), zero, missing or malformed -> ``None``."""
    if not value or not isinstance(value, str):
        return None
    match = _DURATION_RE.match(value.strip().upper())
    if not match or value.strip().upper() in ("P", "PT"):
        return None
    parts = {k: float(v) for k, v in match.groupdict().items() if v}
    total = (
        parts.get("weeks", 0) * 604800
        + parts.get("days", 0) * 86400
        + parts.get("hours", 0) * 3600
        + parts.get("minutes", 0) * 60
        + parts.get("seconds", 0)
    )
    seconds = int(round(total))
    return seconds if seconds > 0 else None


def format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "unknown"
    hours, rem = divmod(int(seconds), 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    return f"{minutes}m {secs:02d}s"
