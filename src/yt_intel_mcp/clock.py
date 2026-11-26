"""Injectable clock so quota resets, cache ages and proposal expiry are testable."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


class Clock:
    """Returns timezone-aware UTC datetimes."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class FakeClock(Clock):
    """Manually advanced clock for tests and benchmarks."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 3, 10, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, **kwargs: float) -> None:
        self._now = self._now + timedelta(**kwargs)

    def set(self, value: datetime) -> None:
        self._now = value
