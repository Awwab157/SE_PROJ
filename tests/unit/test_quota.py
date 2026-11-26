from datetime import UTC, datetime

import pytest

from yt_intel_mcp import quota
from yt_intel_mcp.clock import FakeClock
from yt_intel_mcp.config import load_quota_config
from yt_intel_mcp.errors import InternalError, QuotaBudgetExceeded
from yt_intel_mcp.quota import QuotaConfig, QuotaManager
from yt_intel_mcp.storage import Database


@pytest.fixture
def mgr(tmp_path):
    clock = FakeClock(datetime(2026, 1, 15, 7, 59, tzinfo=UTC))  # 23:59 PST on Jan 14
    return QuotaManager(Database(tmp_path / "q.db"), QuotaConfig(load_quota_config()), clock)


def test_cost_table_loaded(mgr) -> None:
    cfg = mgr.config
    assert cfg.limits == {"search_calls": 100, "units": 10000}
    assert cfg.cost("playlists.insert") == {"units": 50}
    assert cfg.cost("playlistItems.insert") == {"units": 50}
    assert cfg.cost("videos.list") == {"units": 1}
    assert cfg.cost("search.list")["search_calls"] == 1


def test_estimate_and_bucket_separation(mgr) -> None:
    est = mgr.estimate({"search.list": 3, "videos.list": 2, "playlists.insert": 1, "playlistItems.insert": 4})
    assert est["search_calls"] == 3
    assert est["units"] == 3 * mgr.config.cost("search.list")["units"] + 2 + 50 + 200
    assert mgr.estimate({"videos.list": 5})["search_calls"] == 0


def test_unknown_method_is_rejected(mgr) -> None:
    with pytest.raises(InternalError):
        mgr.estimate({"videos.delete": 1})


def test_over_budget_reports_cost_limit_remaining(mgr) -> None:
    with pytest.raises(QuotaBudgetExceeded) as err:
        mgr.reserve({"search.list": 101})
    details = err.value.details
    assert details["estimated"]["search_calls"] == 101
    assert details["limit"]["search_calls"] == 100
    assert details["remaining"]["search_calls"] == 100
    assert "resets_at" in details


def test_reserve_charge_release(mgr) -> None:
    r = mgr.reserve({"videos.list": 5}, label="t")
    assert mgr.status()["buckets"]["units"]["reserved"] == 5
    with quota.active(r):
        quota.charge("videos.list")
        quota.charge("videos.list")
    used = r.release_unused()
    assert used["units"] == 2
    s = mgr.status()["buckets"]["units"]
    assert (s["consumed"], s["reserved"], s["remaining"]) == (2, 0, 9998)


def test_charge_without_reservation_refused() -> None:
    with pytest.raises(InternalError):
        quota.charge("videos.list")


def test_charge_beyond_reservation_refused_but_retry_topup_allowed(mgr) -> None:
    r = mgr.reserve({"videos.list": 1})
    with quota.active(r):
        quota.charge("videos.list")
        with pytest.raises(QuotaBudgetExceeded):
            quota.charge("videos.list")
        quota.charge("videos.list", retry=True)  # retries may top up from the free daily budget
    assert r.release_unused()["units"] == 2


def test_bounded_reservation(mgr) -> None:
    with mgr.db.transaction() as conn:
        mgr._bump(conn, mgr.day_key(), "search_calls", consumed=98)
    r = mgr.reserve({"search.list": 5, "videos.list": 2}, min_plan={"search.list": 1, "videos.list": 2})
    assert r.can_afford("search.list", 2)
    assert not r.can_afford("search.list", 3)
    with pytest.raises(QuotaBudgetExceeded):
        mgr.reserve({"search.list": 5}, min_plan={"search.list": 3})


def test_pacific_midnight_reset(mgr) -> None:
    assert mgr.day_key() == "2026-01-14"
    r = mgr.reserve({"videos.list": 3})
    with quota.active(r):
        for _ in range(3):
            quota.charge("videos.list")
    r.release_unused()
    assert mgr.status()["buckets"]["units"]["consumed"] == 3
    assert mgr.reset_at().isoformat() == "2026-01-15T00:00:00-08:00"
    mgr.clock.advance(minutes=2)  # 00:01 PST
    assert mgr.day_key() == "2026-01-15"
    assert mgr.status()["buckets"]["units"]["consumed"] == 0
    assert mgr.status()["buckets"]["units"]["remaining"] == 10000


def test_mark_exhausted(mgr) -> None:
    r = mgr.reserve({"videos.list": 1})
    with quota.active(r):
        quota.mark_exhausted("videos.list")
    r.release_unused()
    assert mgr.status()["buckets"]["units"]["remaining"] == 0
    with pytest.raises(QuotaBudgetExceeded):
        mgr.reserve({"videos.list": 1})
