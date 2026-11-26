"""Live provider: the ONLY module that imports the Google API client library (NFR-13).

* Maps API errors to typed exceptions.
* Retries *reads* only, only on 429/5xx/rate-limit reasons, at most 3 times with bounded
  exponential backoff. ``quotaExceeded`` and all writes are never retried (FR-6.7, NFR-15).
* Charges quota before every HTTP attempt (``yt_intel_mcp.quota.charge``).
"""

from __future__ import annotations

import json
import random
import time
from collections.abc import Callable
from typing import Any

from google.auth.exceptions import RefreshError, TransportError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from yt_intel_mcp import quota
from yt_intel_mcp.errors import (
    Forbidden,
    InvalidGrant,
    InvalidInput,
    NotFound,
    QuotaExceeded,
    RateLimited,
    Transient,
    WriteScopeRequired,
    YoutubeSignupRequired,
    YTIntelError,
)
from yt_intel_mcp.providers.base import PAGE_SIZE, YouTubeProvider

MAX_RETRIES = 3
BASE_DELAY_SECONDS = 1.0
MAX_DELAY_SECONDS = 8.0
SEARCH_FILTER_KEYS = {
    "relevanceLanguage",
    "videoDuration",
    "videoCategoryId",
    "regionCode",
    "channelId",
    "order",
    "safeSearch",
    "maxResults",
}

_QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded", "dailyLimitExceededUnreg"}
_RATE_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "rateLimitExceededUnreg"}
_NOT_FOUND_REASONS = {
    "videoNotFound",
    "channelNotFound",
    "playlistNotFound",
    "notFound",
    "subscriptionNotFound",
}


def _reason(err: HttpError) -> str | None:
    details = getattr(err, "error_details", None)
    if isinstance(details, list) and details and isinstance(details[0], dict) and details[0].get("reason"):
        return details[0]["reason"]
    try:
        payload = json.loads(err.content.decode("utf-8") if isinstance(err.content, bytes) else err.content)
        errors = payload.get("error", {}).get("errors") or []
        if errors:
            return errors[0].get("reason")
    except (ValueError, AttributeError, TypeError):
        pass
    return None


def map_http_error(err: HttpError) -> YTIntelError:
    status = int(getattr(err.resp, "status", 0) or 0)
    reason = _reason(err)
    if reason in _QUOTA_REASONS:
        return QuotaExceeded("YouTube reported that the daily API quota is exhausted.")
    if reason in _RATE_REASONS or status == 429:
        return RateLimited("YouTube is temporarily rate limiting requests.")
    if reason == "youtubeSignupRequired":
        return YoutubeSignupRequired("The authorised Google account has no YouTube channel.")
    if reason in _NOT_FOUND_REASONS or status == 404:
        return NotFound("The requested YouTube item was not found (it may be private, deleted or terminated).")
    if (
        reason in ("insufficientPermissions", "forbidden", "playlistForbidden", "channelClosed", "channelSuspended")
        or status == 403
    ):
        return Forbidden("YouTube refused access to this item for the authorised account.")
    if status == 401:
        return InvalidGrant("The stored authorisation is no longer valid.")
    if status == 400:
        return InvalidInput("YouTube rejected the request as invalid.")
    if status >= 500:
        return Transient("YouTube returned a temporary server error.")
    return Transient("YouTube returned an unexpected error.")


class LiveProvider(YouTubeProvider):
    def __init__(
        self,
        authorizer: Any,
        *,
        service_factory: Callable[[Any], Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        rng: Callable[[], float] = random.random,
    ) -> None:
        self.authorizer = authorizer
        self._factory = service_factory or (
            lambda creds: build("youtube", "v3", credentials=creds, cache_discovery=False)
        )
        self._sleep = sleep
        self._rng = rng

    def _service(self, write: bool) -> Any:
        return self._factory(self.authorizer.credentials(write=write))

    def _execute(self, api_method: str, make_request: Callable[[Any], Any], *, write: bool = False) -> Any:
        if write and not self.authorizer.has_scope(write=True):
            raise WriteScopeRequired("The current authorisation is read-only; it cannot create playlists.")
        service = self._service(write)
        attempt = 0
        while True:
            quota.charge(api_method, retry=attempt > 0)
            try:
                return make_request(service).execute(num_retries=0)
            except HttpError as exc:
                error = map_http_error(exc)
            except RefreshError:
                error = InvalidGrant("The stored authorisation was revoked or has expired.")
            except (TimeoutError, TransportError, OSError):
                error = Transient("A network error occurred while contacting YouTube.")
            if isinstance(error, QuotaExceeded):
                quota.mark_exhausted(api_method)
                raise error
            retryable = isinstance(error, (RateLimited, Transient))
            if write or not retryable or attempt >= MAX_RETRIES:
                raise error
            delay = min(MAX_DELAY_SECONDS, BASE_DELAY_SECONDS * (2**attempt)) * (0.5 + self._rng() / 2)
            self._sleep(delay)
            attempt += 1

    def _paged(self, api_method: str, make: Callable[[Any, str | None], Any], max_items: int) -> list[Any]:
        items: list[Any] = []
        token: str | None = None
        while True:
            resp = self._execute(api_method, lambda s, t=token: make(s, t))
            items.extend(resp.get("items") or [])
            token = resp.get("nextPageToken")
            if not token or len(items) >= max_items:
                return items[:max_items]

    # --- reads --------------------------------------------------------------------------------
    def get_videos(self, ids):
        out = []
        for start in range(0, len(ids), PAGE_SIZE):
            chunk = ",".join(ids[start : start + PAGE_SIZE])
            resp = self._execute(
                "videos.list",
                lambda s, c=chunk: s.videos().list(part="snippet,contentDetails,status", id=c, maxResults=50),
            )
            out.extend(resp.get("items") or [])
        return out

    def search_videos(self, query, filters=None, page_token=None):
        params = {k: v for k, v in (filters or {}).items() if k in SEARCH_FILTER_KEYS and v is not None}
        params.setdefault("maxResults", 25)
        if page_token:
            params["pageToken"] = page_token
        resp = self._execute("search.list", lambda s: s.search().list(part="snippet", q=query, type="video", **params))
        items = []
        for item in resp.get("items") or []:
            vid = (item.get("id") or {}).get("videoId")
            if not vid:
                continue
            sn = item.get("snippet") or {}
            items.append(
                {
                    "video_id": vid,
                    "title": sn.get("title"),
                    "description": sn.get("description"),
                    "channel_id": sn.get("channelId"),
                    "channel_title": sn.get("channelTitle"),
                }
            )
        return {"items": items, "next_page_token": resp.get("nextPageToken")}

    def search_channels(self, query, max_results=25):
        resp = self._execute(
            "search.list",
            lambda s: s.search().list(part="snippet", q=query, type="channel", maxResults=min(50, max_results)),
        )
        out = []
        for item in resp.get("items") or []:
            cid = (item.get("id") or {}).get("channelId") or (item.get("snippet") or {}).get("channelId")
            if cid:
                sn = item.get("snippet") or {}
                out.append({"channel_id": cid, "title": sn.get("title"), "description": sn.get("description")})
        return out

    def get_channels(self, ids=None, for_handle=None, for_username=None):
        part = "snippet,statistics,contentDetails"
        if ids:
            joined = ",".join(ids[:PAGE_SIZE])
            req = lambda s: s.channels().list(part=part, id=joined, maxResults=50)  # noqa: E731
        elif for_handle:
            req = lambda s: s.channels().list(part=part, forHandle=for_handle)  # noqa: E731
        elif for_username:
            req = lambda s: s.channels().list(part=part, forUsername=for_username)  # noqa: E731
        else:
            return []
        return self._execute("channels.list", req).get("items") or []

    def list_channel_uploads(self, channel_id, max=25):
        channels = (
            self._execute("channels.list", lambda s: s.channels().list(part="contentDetails", id=channel_id)).get(
                "items"
            )
            or []
        )
        if not channels:
            raise NotFound("The channel was not found.")
        uploads = ((channels[0].get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")
        if not uploads:
            return []
        raw = self._paged(
            "playlistItems.list",
            lambda s, t: s.playlistItems().list(
                part="snippet,contentDetails", playlistId=uploads, maxResults=min(50, max), pageToken=t
            ),
            max,
        )
        return [
            {
                "video_id": (i.get("contentDetails") or {}).get("videoId"),
                "title": (i.get("snippet") or {}).get("title"),
                "description": (i.get("snippet") or {}).get("description"),
                "published_at": (i.get("contentDetails") or {}).get("videoPublishedAt"),
            }
            for i in raw
            if (i.get("contentDetails") or {}).get("videoId")
        ]

    def list_liked_videos(self, max_items=1000):
        return self._paged(
            "videos.list",
            lambda s, t: s.videos().list(
                part="snippet,contentDetails,status", myRating="like", maxResults=50, pageToken=t
            ),
            max_items,
        )

    def list_subscriptions(self, max_items=1000):
        raw = self._paged(
            "subscriptions.list",
            lambda s, t: s.subscriptions().list(part="snippet", mine=True, maxResults=50, pageToken=t),
            max_items,
        )
        return [
            {
                "channel_id": ((i.get("snippet") or {}).get("resourceId") or {}).get("channelId"),
                "title": (i.get("snippet") or {}).get("title"),
                "description": (i.get("snippet") or {}).get("description"),
                "subscribed_at": (i.get("snippet") or {}).get("publishedAt"),
            }
            for i in raw
        ]

    def list_playlists(self, max_items=50):
        raw = self._paged(
            "playlists.list",
            lambda s, t: s.playlists().list(part="snippet,contentDetails", mine=True, maxResults=50, pageToken=t),
            max_items,
        )
        return [
            {
                "playlist_id": i["id"],
                "title": (i.get("snippet") or {}).get("title"),
                "item_count": (i.get("contentDetails") or {}).get("itemCount"),
            }
            for i in raw
        ]

    def list_playlist_items(self, playlist_id, max_items=200):
        raw = self._paged(
            "playlistItems.list",
            lambda s, t: s.playlistItems().list(
                part="snippet,contentDetails", playlistId=playlist_id, maxResults=50, pageToken=t
            ),
            max_items,
        )
        return [
            {
                "video_id": (i.get("contentDetails") or {}).get("videoId"),
                "title": (i.get("snippet") or {}).get("title"),
                "added_at": (i.get("snippet") or {}).get("publishedAt"),
                "video_published_at": (i.get("contentDetails") or {}).get("videoPublishedAt"),
            }
            for i in raw
        ]

    def list_video_categories(self, region="US"):
        resp = self._execute(
            "videoCategories.list", lambda s: s.videoCategories().list(part="snippet", regionCode=region)
        )
        return {i["id"]: (i.get("snippet") or {}).get("title") for i in resp.get("items") or []}

    # --- writes (never retried) ---------------------------------------------------------------
    def create_playlist(self, title, description, privacy):
        body = {"snippet": {"title": title, "description": description}, "status": {"privacyStatus": privacy}}
        resp = self._execute(
            "playlists.insert", lambda s: s.playlists().insert(part="snippet,status", body=body), write=True
        )
        return {"playlist_id": resp["id"], "privacy_status": (resp.get("status") or {}).get("privacyStatus")}

    def add_playlist_item(self, playlist_id, video_id):
        body = {
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id},
            }
        }
        resp = self._execute(
            "playlistItems.insert", lambda s: s.playlistItems().insert(part="snippet", body=body), write=True
        )
        return resp.get("id")
