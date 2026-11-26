from datetime import UTC, datetime

from yt_intel_mcp import quota
from yt_intel_mcp.cache import Cache, CachingProvider
from yt_intel_mcp.clock import FakeClock
from yt_intel_mcp.config import load_quota_config
from yt_intel_mcp.quota import QuotaConfig, QuotaManager
from yt_intel_mcp.storage import Database


def setup(tmp_path, provider):
    clock = FakeClock(datetime(2026, 3, 10, 12, tzinfo=UTC))
    db = Database(tmp_path / "c.db")
    cache = Cache(db, clock)
    mgr = QuotaManager(db, QuotaConfig(load_quota_config()), clock)
    return clock, cache, mgr, CachingProvider(provider, cache)


def fetch(mgr, cp, method="get_videos"):
    r = mgr.reserve({"videos.list": 5, "subscriptions.list": 5})
    with quota.active(r):
        if method == "get_videos":
            cp.get_videos(["pdIntro0001"])
        else:
            cp.list_subscriptions()
    r.release_unused()


def test_served_at_23h_refetched_at_25h(tmp_path, provider) -> None:
    clock, cache, mgr, cp = setup(tmp_path, provider)
    fetch(mgr, cp)
    assert provider.count("get_videos") == 1
    clock.advance(hours=23)
    fetch(mgr, cp)
    assert provider.count("get_videos") == 1  # cache hit: no call, no quota
    clock.advance(hours=2)
    fetch(mgr, cp)
    assert provider.count("get_videos") == 2


def test_missing_videos_are_cached_too(tmp_path, provider) -> None:
    _, _, mgr, cp = setup(tmp_path, provider)
    r = mgr.reserve({"videos.list": 2})
    with quota.active(r):
        assert cp.get_videos(["deletedVid1"]) == []
        assert cp.get_videos(["deletedVid1"]) == []
    r.release_unused()
    assert provider.count("get_videos") == 1


def test_purged_after_7_days(tmp_path, provider) -> None:
    clock, cache, mgr, cp = setup(tmp_path, provider)
    fetch(mgr, cp)
    assert cache.count() == 1
    clock.advance(days=6, hours=23)
    assert cache.purge() == 0
    clock.advance(hours=2)
    assert cache.purge() == 1
    assert cache.count() == 0


def test_clear_deletes_account_data(tmp_path, provider) -> None:
    _, cache, mgr, cp = setup(tmp_path, provider)
    fetch(mgr, cp, "subs")
    fetch(mgr, cp)
    assert cache.clear() == 2
    assert cache.count() == 0
