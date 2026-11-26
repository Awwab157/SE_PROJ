"""Quota estimation, atomic reservation and ledger (FR-6).

Workflow:
1. A service builds a *plan* (``{api_method: max_calls}``) and calls :meth:`QuotaManager.reserve`
   before any provider call. Reservation is atomic across all buckets (SQLite ``BEGIN IMMEDIATE``).
   If any bucket cannot cover the (minimum) plan the workflow is rejected with the estimated cost,
   limit and remaining quota, and no API call is made (FR-6.4).
2. Providers call :func:`charge` before every HTTP request. The charge is recorded as consumed even
   if the request then fails (FR-6). A charge outside an active reservation is refused.
3. :meth:`Reservation.release_unused` returns whatever was reserved but not consumed.

Daily buckets reset at midnight America/Los_Angeles (FR-6).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from yt_intel_mcp.clock import Clock
from yt_intel_mcp.errors import InternalError, QuotaBudgetExceeded
from yt_intel_mcp.storage import Database

Plan = Mapping[str, int]


class QuotaConfig:
    def __init__(self, data: Mapping[str, Any]) -> None:
        self.timezone = ZoneInfo(data.get("timezone", "America/Los_Angeles"))
        self.limits: dict[str, int] = {k: int(v) for k, v in data["buckets"].items()}
        self.costs: dict[str, dict[str, int]] = {
            method: {bucket: int(n) for bucket, n in (cost or {}).items()} for method, cost in data["costs"].items()
        }
        for method, cost in self.costs.items():
            unknown = set(cost) - set(self.limits)
            if unknown:
                raise ValueError(f"quota.yaml: {method} uses unknown bucket(s) {sorted(unknown)}")

    def cost(self, api_method: str) -> dict[str, int]:
        if api_method not in self.costs:
            raise InternalError(f"No quota cost configured for {api_method}.")
        return self.costs[api_method]


class QuotaManager:
    def __init__(self, db: Database, config: QuotaConfig, clock: Clock) -> None:
        self.db = db
        self.config = config
        self.clock = clock

    # --- time ----------------------------------------------------------------------------------
    def local_now(self) -> datetime:
        return self.clock.now().astimezone(self.config.timezone)

    def day_key(self) -> str:
        return self.local_now().date().isoformat()

    def reset_at(self) -> datetime:
        local = self.local_now()
        midnight = datetime.combine(local.date() + timedelta(days=1), datetime.min.time(), self.config.timezone)
        return midnight

    # --- estimation ----------------------------------------------------------------------------
    def estimate(self, plan: Plan) -> dict[str, int]:
        totals = {bucket: 0 for bucket in self.config.limits}
        for method, count in plan.items():
            if count <= 0:
                continue
            for bucket, cost in self.config.cost(method).items():
                totals[bucket] += cost * int(count)
        return totals

    def _usage(self, conn, day: str) -> dict[str, tuple[int, int]]:
        rows = conn.execute("SELECT bucket, consumed, reserved FROM quota_ledger WHERE day = ?", (day,))
        usage = {bucket: (0, 0) for bucket in self.config.limits}
        for row in rows:
            usage[row["bucket"]] = (row["consumed"], row["reserved"])
        return usage

    def _remaining(self, usage: dict[str, tuple[int, int]]) -> dict[str, int]:
        return {b: max(0, self.config.limits[b] - c - r) for b, (c, r) in usage.items() if b in self.config.limits}

    @staticmethod
    def _bump(conn, day: str, bucket: str, consumed: int = 0, reserved: int = 0) -> None:
        conn.execute(
            "INSERT INTO quota_ledger(day, bucket, consumed, reserved) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(day, bucket) DO UPDATE SET consumed = consumed + excluded.consumed, "
            "reserved = reserved + excluded.reserved",
            (day, bucket, consumed, reserved),
        )

    # --- reservation ---------------------------------------------------------------------------
    def reserve(self, plan: Plan, *, min_plan: Plan | None = None, label: str = "") -> Reservation:
        """Atomically reserve quota for ``plan``.

        Without ``min_plan`` the reservation is all-or-nothing. With ``min_plan`` the reservation is
        bounded: it fails only if the minimum plan does not fit, otherwise it reserves as much of
        ``plan`` as is available, and the service stops optional calls when that is used up.
        """
        wanted = self.estimate(plan)
        minimum = self.estimate(min_plan) if min_plan is not None else wanted
        day = self.day_key()
        with self.db.transaction() as conn:
            remaining = self._remaining(self._usage(conn, day))
            short = {b: n for b, n in minimum.items() if n > remaining[b]}
            if short:
                raise QuotaBudgetExceeded(
                    "This request would exceed the daily YouTube quota budget: "
                    + "; ".join(
                        f"{b}: estimated {minimum[b]}, limit {self.config.limits[b]}, remaining {remaining[b]}"
                        for b in sorted(short)
                    )
                    + ".",
                    f"Reduce the request size or wait until the quota resets at {self.reset_at().isoformat()}"
                    " (midnight Pacific Time).",
                    details={
                        "estimated": minimum,
                        "limit": dict(self.config.limits),
                        "remaining": remaining,
                        "resets_at": self.reset_at().isoformat(),
                    },
                )
            granted = {b: min(wanted[b], remaining[b]) if min_plan is not None else wanted[b] for b in wanted}
            granted = {b: max(granted[b], minimum[b]) for b in granted}
            rid = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO reservations(id, day, label, created_at, status, remaining, consumed) "
                "VALUES (?, ?, ?, ?, 'active', ?, ?)",
                (
                    rid,
                    day,
                    label,
                    self.clock.now().isoformat(),
                    json.dumps(granted),
                    json.dumps({b: 0 for b in granted}),
                ),
            )
            for bucket, n in granted.items():
                if n:
                    self._bump(conn, day, bucket, reserved=n)
        return Reservation(self, rid, day, label)

    def mark_exhausted(self, api_method: str) -> None:
        """Called when YouTube reports ``quotaExceeded``: no further calls today for those buckets."""
        day = self.day_key()
        buckets = [b for b, n in self.config.cost(api_method).items() if n > 0]
        with self.db.transaction() as conn:
            usage = self._usage(conn, day)
            for bucket in buckets:
                consumed, _reserved = usage[bucket]
                # Mark the whole day as consumed so nothing else is attempted until the reset.
                self._bump(conn, day, bucket, consumed=max(0, self.config.limits[bucket] - consumed))

    def status(self) -> dict[str, Any]:
        day = self.day_key()
        with self.db.read() as conn:
            usage = self._usage(conn, day)
        remaining = self._remaining(usage)
        return {
            "day": day,
            "timezone": str(self.config.timezone),
            "resets_at": self.reset_at().isoformat(),
            "buckets": {
                b: {
                    "limit": self.config.limits[b],
                    "consumed": usage[b][0],
                    "reserved": usage[b][1],
                    "remaining": remaining[b],
                }
                for b in self.config.limits
            },
        }


class Reservation:
    def __init__(self, manager: QuotaManager, rid: str, day: str, label: str) -> None:
        self.manager = manager
        self.id = rid
        self.day = day
        self.label = label

    def _load(self, conn) -> tuple[str, dict[str, int], dict[str, int]]:
        row = conn.execute("SELECT status, remaining, consumed FROM reservations WHERE id = ?", (self.id,)).fetchone()
        return row["status"], json.loads(row["remaining"]), json.loads(row["consumed"])

    def can_afford(self, api_method: str, count: int = 1, keep: Plan | None = None) -> bool:
        """True if ``count`` calls fit in what is left of this reservation, after keeping ``keep``."""
        need = self.manager.estimate({api_method: count})
        kept = self.manager.estimate(keep or {})
        with self.manager.db.read() as conn:
            status, remaining, _ = self._load(conn)
        if status != "active":
            return False
        return all(remaining.get(b, 0) - kept[b] >= n for b, n in need.items())

    def charge(self, api_method: str, *, retry: bool = False) -> None:
        """Record one API call as consumed. Retries may top up from the free daily budget."""
        cost = self.manager.config.cost(api_method)
        mgr = self.manager
        with mgr.db.transaction() as conn:
            status, remaining, consumed = self._load(conn)
            if status != "active":
                raise InternalError("Quota reservation is closed; no API call was made.")
            free = mgr._remaining(mgr._usage(conn, self.day))
            from_reserved: dict[str, int] = {}
            from_free: dict[str, int] = {}
            for bucket, n in cost.items():
                take = min(n, remaining.get(bucket, 0))
                from_reserved[bucket] = take
                from_free[bucket] = n - take
            if any(from_free.values()):
                if not retry or any(from_free[b] > free[b] for b in from_free):
                    raise QuotaBudgetExceeded(
                        f"The quota reserved for this request is used up before {api_method}.",
                        "Reduce the request size or wait for the daily reset.",
                        details={"api_method": api_method, "reservation_remaining": remaining},
                    )
            for bucket, n in cost.items():
                remaining[bucket] = remaining.get(bucket, 0) - from_reserved[bucket]
                consumed[bucket] = consumed.get(bucket, 0) + n
                mgr._bump(conn, self.day, bucket, consumed=n, reserved=-from_reserved[bucket])
            conn.execute(
                "UPDATE reservations SET remaining = ?, consumed = ? WHERE id = ?",
                (json.dumps(remaining), json.dumps(consumed), self.id),
            )
            conn.execute(
                "INSERT INTO quota_events(ts, reservation_id, api_method, cost) VALUES (?, ?, ?, ?)",
                (mgr.clock.now().isoformat(), self.id, api_method, json.dumps(cost)),
            )

    def consumed(self) -> dict[str, int]:
        with self.manager.db.read() as conn:
            _, _, consumed = self._load(conn)
        return consumed

    def release_unused(self) -> dict[str, int]:
        """Return unused reserved quota to the day's budget. Consumed quota stays consumed."""
        with self.manager.db.transaction() as conn:
            status, remaining, consumed = self._load(conn)
            if status == "active":
                for bucket, n in remaining.items():
                    if n:
                        self.manager._bump(conn, self.day, bucket, reserved=-n)
                conn.execute(
                    "UPDATE reservations SET status = 'closed', remaining = ? WHERE id = ?",
                    (json.dumps({b: 0 for b in remaining}), self.id),
                )
        return consumed


# --- context-local active reservation --------------------------------------------------------------

_active: ContextVar[Reservation | None] = ContextVar("yt_intel_active_reservation", default=None)


@contextmanager
def active(reservation: Reservation) -> Iterator[Reservation]:
    token = _active.set(reservation)
    try:
        yield reservation
    finally:
        _active.reset(token)


def current() -> Reservation:
    reservation = _active.get()
    if reservation is None:
        raise InternalError("API call attempted without a quota reservation; no call was made.")
    return reservation


def charge(api_method: str, *, retry: bool = False) -> None:
    current().charge(api_method, retry=retry)


def can_afford(api_method: str, count: int = 1, keep: Plan | None = None) -> bool:
    return current().can_afford(api_method, count, keep)


def mark_exhausted(api_method: str) -> None:
    reservation = _active.get()
    if reservation is not None:
        reservation.manager.mark_exhausted(api_method)
