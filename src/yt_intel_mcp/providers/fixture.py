"""Fixture provider: serves synthetic JSON from ``tests/fixtures`` and records every call.

Used by all CI tests (no network), by ``local-check`` and by ``scripts/benchmark.py``. It charges
quota exactly like the live provider (one charge per emulated page) and can inject errors.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from yt_intel_mcp import quota
from yt_intel_mcp.config import repo_root
from yt_intel_mcp.duration import parse_duration
from yt_intel_mcp.errors import NotFound
from yt_intel_mcp.providers.base import API_METHODS, PAGE_SIZE, WRITE_METHODS, YouTubeProvider

FIXTURES_ENV = "YT_INTEL_FIXTURES"
_STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "for", "with", "on", "how", "what", "is"}


def default_fixtures_dir() -> Path:
    override = os.environ.get(FIXTURES_ENV)
    return Path(override) if override else repo_root() / "tests" / "fixtures"


def load_fixture_data(directory: Path | None = None) -> dict[str, Any]:
    directory = directory or default_fixtures_dir()
    data: dict[str, Any] = {}
    for name in ("videos", "channels", "account", "categories", "search_only"):
        path = directory / f"{name}.json"
        data[name] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    return data


def _tokens(text: str | None) -> list[str]:
    return [t for t in re.findall(r"[^\W\d_]+", (text or "").lower()) if t not in _STOP]


def _duration_class(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    if seconds < 240:
        return "short"
    if seconds <= 1200:
        return "medium"
    return "long"


class FixtureProvider(YouTubeProvider):
    def __init__(self, data: dict[str, Any] | None = None, *, authorizer: Any = None) -> None:
        data = data if data is not None else load_fixture_data()
        self.videos: dict[str, dict[str, Any]] = {v["id"]: v for v in (data.get("videos") or [])}
        self.channels: dict[str, dict[str, Any]] = {c["id"]: c for c in (data.get("channels") or [])}
        self.search_only: list[dict[str, Any]] = list(data.get("search_only") or [])
        account = data.get("account") or {}
        self.liked_ids: list[str] = list(account.get("liked_video_ids") or [])
        self.subscriptions: list[dict[str, Any]] = list(account.get("subscriptions") or [])
        self.playlists: list[dict[str, Any]] = [dict(p) for p in (account.get("playlists") or [])]
        self.categories: dict[str, dict[str, str]] = data.get("categories") or {}
        self.authorizer = authorizer
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.errors: dict[str, list[BaseException]] = {}
        self.created_playlists: list[dict[str, Any]] = []
        self.inserted_items: list[tuple[str, str]] = []

    # --- test helpers -------------------------------------------------------------------------
    def inject_error(self, method: str, error: BaseException, times: int = 1) -> None:
        self.errors.setdefault(method, []).extend([error] * times)

    def count(self, method: str) -> int:
        return sum(1 for m, _ in self.calls if m == method)

    @property
    def write_calls(self) -> list[tuple[str, dict[str, Any]]]:
        return [c for c in self.calls if c[0] in WRITE_METHODS]

    def _call(self, method: str, args: dict[str, Any]) -> None:
        write = method in WRITE_METHODS
        if self.authorizer is not None:
            self.authorizer.credentials(write=write)
        quota.charge(API_METHODS[method])
        self.calls.append((method, args))
        queue = self.errors.get(method)
        if queue:
            raise queue.pop(0)

    def _pages(self, method: str, items: list[Any], max_items: int, args: dict[str, Any]) -> list[Any]:
        items = items[:max_items]
        pages = max(1, -(-len(items) // PAGE_SIZE))
        for page in range(pages):
            self._call(method, {**args, "page": page})
        return items

    # --- reads --------------------------------------------------------------------------------
    def get_videos(self, ids: list[str]) -> list[dict[str, Any]]:
        out = []
        for start in range(0, len(ids), PAGE_SIZE):
            chunk = ids[start : start + PAGE_SIZE]
            self._call("get_videos", {"ids": list(chunk)})
            out.extend(json.loads(json.dumps(self.videos[v])) for v in chunk if v in self.videos)
        return out

    def _search_pool(self) -> list[dict[str, Any]]:
        pool = []
        for v in self.videos.values():
            if v.get("_hidden_from_search"):
                continue
            sn = v.get("snippet") or {}
            pool.append(
                {
                    "video_id": v["id"],
                    "title": sn.get("title"),
                    "description": sn.get("description"),
                    "channel_id": sn.get("channelId"),
                    "channel_title": sn.get("channelTitle"),
                    "_tags": sn.get("tags") or [],
                    "_category": sn.get("categoryId"),
                    "_duration": parse_duration((v.get("contentDetails") or {}).get("duration")),
                }
            )
        for s in self.search_only:
            pool.append({**s, "_tags": s.get("tags") or [], "_category": None, "_duration": None})
        return pool

    def search_videos(self, query, filters=None, page_token=None):
        filters = dict(filters or {})
        self._call("search_videos", {"query": query, "filters": filters, "page_token": page_token})
        per_page = min(int(filters.get("maxResults", 25)), 50)
        terms = set(_tokens(query))
        ranked = []
        for item in self._search_pool():
            if filters.get("videoCategoryId") and item["_category"] != str(filters["videoCategoryId"]):
                continue
            if filters.get("channelId") and item["channel_id"] != filters["channelId"]:
                continue
            if filters.get("videoDuration") and _duration_class(item["_duration"]) != filters["videoDuration"]:
                continue
            title = set(_tokens(item["title"]))
            body = set(_tokens(item["description"])) | set(_tokens(" ".join(item["_tags"])))
            score = 2 * len(terms & title) + len(terms & body)
            if score > 0:
                ranked.append((-score, item["video_id"], item))
        ranked.sort(key=lambda r: (r[0], r[1]))
        offset = int(page_token or 0)
        page = [{k: v for k, v in r[2].items() if not k.startswith("_")} for r in ranked[offset : offset + per_page]]
        next_token = str(offset + per_page) if offset + per_page < len(ranked) else None
        return {"items": page, "next_page_token": next_token}

    def search_channels(self, query, max_results=25):
        self._call("search_channels", {"query": query, "max": max_results})
        terms = set(_tokens(query))
        ranked = []
        for c in self.channels.values():
            if c.get("_terminated"):
                continue
            sn = c.get("snippet") or {}
            score = (
                2 * len(terms & set(_tokens(sn.get("title"))))
                + 2 * len(terms & set(_tokens(sn.get("customUrl"))))
                + len(terms & set(_tokens(sn.get("description"))))
            )
            if score > 0:
                ranked.append((-score, c["id"], sn))
        ranked.sort(key=lambda r: (r[0], r[1]))
        return [
            {"channel_id": cid, "title": sn.get("title"), "description": sn.get("description")}
            for _, cid, sn in ranked[:max_results]
        ]

    def get_channels(self, ids=None, for_handle=None, for_username=None):
        self._call("get_channels", {"ids": ids, "handle": for_handle, "username": for_username})
        live = [c for c in self.channels.values() if not c.get("_terminated")]
        if ids:
            found = [c for c in live if c["id"] in ids]
        elif for_handle:
            handle = for_handle.lower().lstrip("@")
            found = [c for c in live if (c["snippet"].get("customUrl") or "").lower().lstrip("@") == handle]
        elif for_username:
            found = [c for c in live if (c.get("_username") or "").lower() == for_username.lower()]
        else:
            found = []
        return [{k: v for k, v in json.loads(json.dumps(c)).items() if not k.startswith("_")} for c in found]

    def list_channel_uploads(self, channel_id, max=25):
        channel = self.channels.get(channel_id)
        self._call("get_channels", {"ids": [channel_id], "purpose": "uploads"})
        if channel is None or channel.get("_terminated"):
            raise NotFound("The channel was not found.")
        uploads = sorted(
            (v for v in self.videos.values() if (v.get("snippet") or {}).get("channelId") == channel_id),
            key=lambda v: (v["snippet"].get("publishedAt") or "", v["id"]),
            reverse=True,
        )
        items = [
            {
                "video_id": v["id"],
                "title": v["snippet"].get("title"),
                "description": v["snippet"].get("description"),
                "published_at": v["snippet"].get("publishedAt"),
            }
            for v in uploads
        ]
        return self._pages("list_channel_uploads", items, max, {"channel": channel_id})

    def list_liked_videos(self, max_items=1000):
        liked = [json.loads(json.dumps(self.videos[v])) for v in self.liked_ids if v in self.videos]
        return self._pages("list_liked_videos", liked, max_items, {})

    def list_subscriptions(self, max_items=1000):
        return self._pages("list_subscriptions", [dict(s) for s in self.subscriptions], max_items, {})

    def list_playlists(self, max_items=50):
        items = [
            {
                "playlist_id": p["playlist_id"],
                "title": p.get("title"),
                "item_count": len(p.get("items") or []),
            }
            for p in self.playlists
        ]
        return self._pages("list_playlists", items, max_items, {})

    def list_playlist_items(self, playlist_id, max_items=200):
        playlist = next((p for p in self.playlists if p["playlist_id"] == playlist_id), None)
        if playlist is None:
            self._call("list_playlist_items", {"playlist": playlist_id})
            raise NotFound("The playlist was not found.")
        items = [dict(i) for i in (playlist.get("items") or [])]
        return self._pages("list_playlist_items", items, max_items, {"playlist": playlist_id})

    def list_video_categories(self, region="US"):
        self._call("list_video_categories", {"region": region})
        return dict(self.categories.get(region) or self.categories.get("US") or {})

    # --- writes -------------------------------------------------------------------------------
    def create_playlist(self, title, description, privacy):
        self._call("create_playlist", {"title": title, "privacy": privacy})
        playlist_id = "PL" + f"{len(self.created_playlists) + 1:032x}"
        record = {
            "playlist_id": playlist_id,
            "title": title,
            "description": description,
            "privacy": privacy,
            "items": [],
        }
        self.created_playlists.append(record)
        self.playlists.append(record)
        return {"playlist_id": playlist_id, "privacy_status": privacy}

    def add_playlist_item(self, playlist_id, video_id):
        self._call("add_playlist_item", {"playlist": playlist_id, "video": video_id})
        playlist = next((p for p in self.playlists if p["playlist_id"] == playlist_id), None)
        if playlist is None or video_id not in self.videos:
            raise NotFound("The playlist or video was not found.")
        playlist["items"].append({"video_id": video_id, "title": None, "added_at": None})
        self.inserted_items.append((playlist_id, video_id))
        return f"item-{len(self.inserted_items)}"
