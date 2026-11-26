"""Response cache (FR-6.6): serve entries up to 24 h old, refetch after, purge after 7 days.

``clear_cache`` and ``revoke_authorization`` delete all cached account data (NFR-11).
Writes are never cached; playlist listings are invalidated after a playlist is created.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable
from typing import Any

from yt_intel_mcp.clock import Clock
from yt_intel_mcp.providers.base import YouTubeProvider
from yt_intel_mcp.storage import Database

SERVE_SECONDS = 24 * 3600
PURGE_SECONDS = 7 * 24 * 3600
_MISSING = {"__missing__": True}


class Cache:
    def __init__(self, db: Database, clock: Clock) -> None:
        self.db = db
        self.clock = clock
        self.purge()

    @staticmethod
    def key(method: str, args: Any) -> str:
        raw = json.dumps([method, args], sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _now(self) -> float:
        return self.clock.now().timestamp()

    def get(self, method: str, args: Any) -> tuple[bool, Any]:
        with self.db.read() as conn:
            row = conn.execute(
                "SELECT value, fetched_at FROM cache WHERE key = ?", (self.key(method, args),)
            ).fetchone()
        if row is None or self._now() - row["fetched_at"] > SERVE_SECONDS:
            return False, None
        return True, json.loads(row["value"])

    def put(self, method: str, args: Any, value: Any) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache(key, method, value, fetched_at) VALUES (?, ?, ?, ?)",
                (self.key(method, args), method, json.dumps(value), self._now()),
            )

    def purge(self) -> int:
        with self.db.transaction() as conn:
            cur = conn.execute("DELETE FROM cache WHERE fetched_at < ?", (self._now() - PURGE_SECONDS,))
            return cur.rowcount

    def invalidate(self, methods: list[str]) -> None:
        with self.db.transaction() as conn:
            conn.executemany("DELETE FROM cache WHERE method = ?", [(m,) for m in methods])

    def clear(self) -> int:
        with self.db.transaction() as conn:
            return conn.execute("DELETE FROM cache").rowcount

    def count(self) -> int:
        with self.db.read() as conn:
            return conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]


class CachingProvider(YouTubeProvider):
    """Wraps a provider; cache hits make no API call and consume no quota."""

    def __init__(self, inner: YouTubeProvider, cache: Cache) -> None:
        self.inner = inner
        self.cache = cache

    def _cached(self, method: str, args: dict[str, Any], fetch: Callable[[], Any]) -> Any:
        hit, value = self.cache.get(method, args)
        if hit:
            return copy.deepcopy(value)
        value = fetch()
        self.cache.put(method, args, value)
        return value

    def get_videos(self, ids: list[str]) -> list[dict[str, Any]]:
        found: dict[str, dict[str, Any] | None] = {}
        missing: list[str] = []
        for vid in dict.fromkeys(ids):
            hit, value = self.cache.get("video", vid)
            if hit:
                found[vid] = None if value == _MISSING else value
            else:
                missing.append(vid)
        if missing:
            fetched = {item["id"]: item for item in self.inner.get_videos(missing)}
            for vid in missing:
                item = fetched.get(vid)
                self.cache.put("video", vid, item if item is not None else _MISSING)
                found[vid] = item
        return [copy.deepcopy(found[v]) for v in dict.fromkeys(ids) if found.get(v) is not None]

    def search_videos(self, query, filters=None, page_token=None):
        args = {"query": query, "filters": filters or {}, "page_token": page_token}
        return self._cached("search_videos", args, lambda: self.inner.search_videos(query, filters, page_token))

    def search_channels(self, query, max_results=25):
        return self._cached(
            "search_channels",
            {"query": query, "max": max_results},
            lambda: self.inner.search_channels(query, max_results),
        )

    def get_channels(self, ids=None, for_handle=None, for_username=None):
        args = {"ids": sorted(ids or []), "handle": for_handle, "username": for_username}
        return self._cached("get_channels", args, lambda: self.inner.get_channels(ids, for_handle, for_username))

    def list_channel_uploads(self, channel_id, max=25):
        return self._cached(
            "list_channel_uploads",
            {"channel": channel_id, "max": max},
            lambda: self.inner.list_channel_uploads(channel_id, max),
        )

    def list_liked_videos(self, max_items=1000):
        return self._cached("list_liked_videos", {"max": max_items}, lambda: self.inner.list_liked_videos(max_items))

    def list_subscriptions(self, max_items=1000):
        return self._cached("list_subscriptions", {"max": max_items}, lambda: self.inner.list_subscriptions(max_items))

    def list_playlists(self, max_items=50):
        return self._cached("list_playlists", {"max": max_items}, lambda: self.inner.list_playlists(max_items))

    def list_playlist_items(self, playlist_id, max_items=200):
        return self._cached(
            "list_playlist_items",
            {"playlist": playlist_id, "max": max_items},
            lambda: self.inner.list_playlist_items(playlist_id, max_items),
        )

    def list_video_categories(self, region="US"):
        return self._cached(
            "list_video_categories", {"region": region}, lambda: self.inner.list_video_categories(region)
        )

    # Writes pass straight through and are never cached.
    def create_playlist(self, title, description, privacy):
        result = self.inner.create_playlist(title, description, privacy)
        self.cache.invalidate(["list_playlists"])
        return result

    def add_playlist_item(self, playlist_id, video_id):
        result = self.inner.add_playlist_item(playlist_id, video_id)
        self.cache.invalidate(["list_playlist_items"])
        return result
