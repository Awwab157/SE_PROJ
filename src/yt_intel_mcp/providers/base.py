"""Provider interface (SE-6).

Deliberately small: there are no update/delete methods (NFR-5) and no watch-history access
(FR-3.7). Implementations must call :func:`yt_intel_mcp.quota.charge` before every API request.

Return shapes (identical for live and fixture providers):
* ``get_videos`` / ``list_liked_videos`` -> raw ``videos`` resources (snippet, contentDetails, status)
* ``get_channels`` -> raw ``channels`` resources (snippet, statistics, contentDetails)
* ``search_videos`` -> ``{"items": [{video_id, title, description, channel_id, channel_title}],
  "next_page_token": str | None}``
* ``search_channels`` -> ``[{channel_id, title, description}]``
* ``list_channel_uploads`` -> ``[{video_id, title, description, published_at}]``
* ``list_subscriptions`` -> ``[{channel_id, title, description, subscribed_at}]``
* ``list_playlists`` -> ``[{playlist_id, title, item_count}]``
* ``list_playlist_items`` -> ``[{video_id, title, added_at, video_published_at}]``
* ``list_video_categories`` -> ``{category_id: title}``
* ``create_playlist`` -> ``{playlist_id, privacy_status}``; ``add_playlist_item`` -> item ID
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

# Provider method -> YouTube API method (used for quota costs and documentation).
API_METHODS: dict[str, str] = {
    "get_videos": "videos.list",
    "search_videos": "search.list",
    "search_channels": "search.list",
    "get_channels": "channels.list",
    "list_channel_uploads": "playlistItems.list",
    "list_liked_videos": "videos.list",
    "list_subscriptions": "subscriptions.list",
    "list_playlists": "playlists.list",
    "list_playlist_items": "playlistItems.list",
    "list_video_categories": "videoCategories.list",
    "create_playlist": "playlists.insert",
    "add_playlist_item": "playlistItems.insert",
}
WRITE_METHODS = frozenset({"create_playlist", "add_playlist_item"})
READ_METHODS = frozenset(API_METHODS) - WRITE_METHODS
PAGE_SIZE = 50


class YouTubeProvider(ABC):
    @abstractmethod
    def get_videos(self, ids: list[str]) -> list[dict[str, Any]]: ...

    @abstractmethod
    def search_videos(
        self, query: str, filters: dict[str, Any] | None = None, page_token: str | None = None
    ) -> dict[str, Any]: ...

    @abstractmethod
    def search_channels(self, query: str, max_results: int = 25) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_channels(
        self,
        ids: list[str] | None = None,
        for_handle: str | None = None,
        for_username: str | None = None,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    def list_channel_uploads(self, channel_id: str, max: int = 25) -> list[dict[str, Any]]: ...

    @abstractmethod
    def list_liked_videos(self, max_items: int = 1000) -> list[dict[str, Any]]: ...

    @abstractmethod
    def list_subscriptions(self, max_items: int = 1000) -> list[dict[str, Any]]: ...

    @abstractmethod
    def list_playlists(self, max_items: int = 50) -> list[dict[str, Any]]: ...

    @abstractmethod
    def list_playlist_items(self, playlist_id: str, max_items: int = 200) -> list[dict[str, Any]]: ...

    @abstractmethod
    def list_video_categories(self, region: str = "US") -> dict[str, str]: ...

    @abstractmethod
    def create_playlist(self, title: str, description: str, privacy: str) -> dict[str, Any]: ...

    @abstractmethod
    def add_playlist_item(self, playlist_id: str, video_id: str) -> str: ...


def pages_for(max_items: int, page_size: int = PAGE_SIZE) -> int:
    """Upper bound of list calls needed to read ``max_items`` (at least one call)."""
    return max(1, -(-int(max_items) // page_size))
