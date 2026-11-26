"""Pydantic input/output models (FR-8.3) and normalisation of API resources.

All text that comes from YouTube (titles, descriptions, tags, channel names) is untrusted data: it is
copied into results as data only and never interpreted (FR-5.10).
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from yt_intel_mcp.duration import parse_duration
from yt_intel_mcp.ids import video_url

# ISO 639-1 two-letter codes (FR-5.1).
ISO_639_1 = frozenset(
    "aa ab ae af ak am an ar as av ay az ba be bg bh bi bm bn bo br bs ca ce ch co cr cs cu cv cy da de dv dz "
    "ee el en eo es et eu fa ff fi fj fo fr fy ga gd gl gn gu gv ha he hi ho hr ht hu hy hz ia id ie ig ii ik "
    "io is it iu ja jv ka kg ki kj kk kl km kn ko kr ks ku kv kw ky la lb lg li ln lo lt lu lv mg mh mi mk ml "
    "mn mr ms mt my na nb nd ne ng nl nn no nr nv ny oc oj om or os pa pi pl ps pt qu rm rn ro ru rw sa sc sd "
    "se sg si sk sl sm sn so sq sr ss st su sv sw ta te tg th ti tk tl tn to tr ts tt tw ty ug uk ur uz ve vi "
    "vo wa wo xh yi yo za zh zu".split()
)

PRIVACY = Literal["private", "unlisted", "public"]


def primary_language(code: str | None) -> str | None:
    """``en-US`` -> ``en``; unknown/not-applicable codes -> ``None``."""
    if not code or not isinstance(code, str):
        return None
    primary = re.split(r"[-_]", code.strip().lower())[0]
    if primary in ("", "und", "zxx", "mul"):
        return None
    return primary


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ==================================================================================================
# Normalised metadata
# ==================================================================================================


class VideoMeta(BaseModel):
    video_id: str
    title: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    channel_id: str | None = None
    channel_title: str | None = None
    category_id: str | None = None
    duration_seconds: int | None = None
    language: str | None = None
    published_at: str | None = None
    privacy_status: str | None = None
    upload_status: str | None = None
    live_broadcast_content: str | None = None
    available: bool = True
    unavailable_fields: list[str] = Field(default_factory=list)

    @property
    def url(self) -> str:
        return video_url(self.video_id)


def video_from_api(item: dict[str, Any]) -> VideoMeta:
    snippet = item.get("snippet") or {}
    details = item.get("contentDetails") or {}
    status = item.get("status") or {}
    tags = [t for t in (snippet.get("tags") or []) if isinstance(t, str) and t.strip()]
    language = primary_language(snippet.get("defaultAudioLanguage")) or primary_language(snippet.get("defaultLanguage"))
    privacy = status.get("privacyStatus")
    upload = status.get("uploadStatus")
    live = snippet.get("liveBroadcastContent")
    duration = parse_duration(details.get("duration"))
    available = privacy not in ("private",) and upload in (None, "processed")
    meta = VideoMeta(
        video_id=item["id"],
        title=(snippet.get("title") or None),
        description=(snippet.get("description") or None),
        tags=tags,
        channel_id=snippet.get("channelId"),
        channel_title=snippet.get("channelTitle"),
        category_id=snippet.get("categoryId"),
        duration_seconds=duration,
        language=language,
        published_at=snippet.get("publishedAt"),
        privacy_status=privacy,
        upload_status=upload,
        live_broadcast_content=live,
        available=available,
    )
    unavailable = []
    for field, present in (
        ("title", meta.title),
        ("description", meta.description),
        ("tags", meta.tags),
        ("category", meta.category_id),
        ("duration", meta.duration_seconds),
        ("language", meta.language),
    ):
        if not present:
            unavailable.append(field)
    meta.unavailable_fields = unavailable
    return meta


class ChannelMeta(BaseModel):
    channel_id: str
    title: str | None = None
    description: str | None = None
    custom_url: str | None = None
    language: str | None = None
    subscriber_count: int | None = None
    video_count: int | None = None
    uploads_playlist_id: str | None = None


def channel_from_api(item: dict[str, Any]) -> ChannelMeta:
    snippet = item.get("snippet") or {}
    stats = item.get("statistics") or {}
    related = (item.get("contentDetails") or {}).get("relatedPlaylists") or {}
    subscribers = None
    if not stats.get("hiddenSubscriberCount") and stats.get("subscriberCount") is not None:
        try:
            subscribers = int(stats["subscriberCount"])
        except (TypeError, ValueError):
            subscribers = None
    videos = None
    if stats.get("videoCount") is not None:
        try:
            videos = int(stats["videoCount"])
        except (TypeError, ValueError):
            videos = None
    return ChannelMeta(
        channel_id=item["id"],
        title=snippet.get("title") or None,
        description=snippet.get("description") or None,
        custom_url=snippet.get("customUrl"),
        language=primary_language(snippet.get("defaultLanguage")),
        subscriber_count=subscribers,
        video_count=videos,
        uploads_playlist_id=related.get("uploads"),
    )


# ==================================================================================================
# Inputs
# ==================================================================================================


class FindSimilarVideosInput(_Strict):
    video: str = Field(min_length=1, max_length=2048)
    limit: int = Field(default=10, ge=1, le=50)


class FindSimilarChannelsInput(_Strict):
    channel: str = Field(min_length=1, max_length=2048)
    limit: int = Field(default=10, ge=1, le=50)


class RecommendFilters(_Strict):
    max_duration_min: float | None = Field(default=None, gt=0, le=1440)
    language: str | None = None
    category: str | None = Field(default=None, pattern=r"^\d{1,4}$")

    @field_validator("language")
    @classmethod
    def _lang(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.lower()
        if value not in ISO_639_1:
            raise ValueError("language must be an ISO 639-1 code such as 'en' or 'de'")
        return value


class RecommendVideosInput(_Strict):
    limit: int = Field(default=10, ge=1, le=50)
    filters: RecommendFilters = Field(default_factory=RecommendFilters)


PERIOD_PATTERN = (
    r"^(all|last_\d{1,4}_days|\d{4}|\d{4}-Q[1-4]|\d{4}-(0[1-9]|1[0-2])|\d{4}-\d{2}-\d{2}\.\.\d{4}-\d{2}-\d{2})$"
)


class AnalyzeEngagementInput(_Strict):
    period: str = Field(default="all", pattern=PERIOD_PATTERN)
    compare_to: str | None = Field(default=None, pattern=PERIOD_PATTERN)


class ProposePlaylistInput(_Strict):
    topic: str = Field(min_length=3, max_length=100)
    total_duration_min: float = Field(gt=0, le=1440)
    max_video_duration_min: float = Field(gt=0, le=1440)
    language: str
    min_video_duration_min: float | None = Field(default=None, gt=0, le=1440)
    privacy: PRIVACY = "private"

    @field_validator("language")
    @classmethod
    def _lang(cls, value: str) -> str:
        value = value.lower()
        if value not in ISO_639_1:
            raise ValueError("language must be an ISO 639-1 code such as 'en' or 'de'")
        return value

    @model_validator(mode="after")
    def _durations(self) -> ProposePlaylistInput:
        if self.max_video_duration_min > self.total_duration_min:
            raise ValueError("max_video_duration_min must not exceed total_duration_min")
        if self.min_video_duration_min is not None and self.min_video_duration_min > self.max_video_duration_min:
            raise ValueError("min_video_duration_min must not exceed max_video_duration_min")
        return self


class CreatePlaylistInput(_Strict):
    proposal_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    confirmation_code: str | None = Field(default=None, max_length=64)


# ==================================================================================================
# Outputs (UI-1: structured content + a short human-readable ``summary``)
# ==================================================================================================


class ErrorInfo(BaseModel):
    code: str
    cause: str
    next_step: str
    details: dict[str, Any] = Field(default_factory=dict)


class VideoSummary(BaseModel):
    video_id: str
    title: str | None
    channel_id: str | None
    channel_title: str | None
    url: str
    duration_seconds: int | None
    published_at: str | None = None
    language: str | None = None
    category_id: str | None = None


def summary_of(video: VideoMeta) -> dict[str, Any]:
    return {
        "video_id": video.video_id,
        "title": video.title,
        "channel_id": video.channel_id,
        "channel_title": video.channel_title,
        "url": video.url,
        "duration_seconds": video.duration_seconds,
        "published_at": video.published_at,
        "language": video.language,
        "category_id": video.category_id,
    }


class SimilarVideo(VideoSummary):
    score: float
    components: dict[str, float]
    explanation: str


class SeedVideo(BaseModel):
    video_id: str
    title: str | None
    channel_title: str | None
    url: str
    unavailable_fields: list[str]


class FindSimilarVideosResult(BaseModel):
    status: Literal["ok", "insufficient_metadata", "no_candidates"]
    summary: str
    seed: SeedVideo
    results: list[SimilarVideo]
    excluded: dict[str, int]
    notes: list[str]
    quota_used: dict[str, int] = Field(default_factory=dict)
    writes_to_youtube: bool = False


class ChannelRefOut(BaseModel):
    channel_id: str
    title: str | None
    url: str


class SimilarChannel(BaseModel):
    channel_id: str
    title: str | None
    url: str
    subscriber_count: int | None
    score: float
    secondary_score: float
    explanation: str


class FindSimilarChannelsResult(BaseModel):
    status: Literal["ok", "ambiguous_channel", "insufficient_metadata", "no_candidates"]
    summary: str
    seed: ChannelRefOut | None
    results: list[SimilarChannel]
    candidates: list[ChannelRefOut] = Field(default_factory=list)
    notes: list[str]
    quota_used: dict[str, int] = Field(default_factory=dict)
    writes_to_youtube: bool = False


class Recommendation(VideoSummary):
    score: float
    signals: list[str]


class InterestProfile(BaseModel):
    top_terms: list[str]
    top_channels: list[str]
    top_categories: list[str]
    signal_counts: dict[str, int]


class RecommendVideosResult(BaseModel):
    status: Literal["ok", "empty_account", "no_candidates"]
    summary: str
    results: list[Recommendation]
    profile: InterestProfile | None
    excluded: dict[str, int]
    notes: list[str]
    data_limits: list[str]
    quota_used: dict[str, int] = Field(default_factory=dict)
    writes_to_youtube: bool = False


class CountShare(BaseModel):
    key: str
    label: str | None
    count: int
    share: float


class TrendPoint(BaseModel):
    period: str
    count: int


class Trend(BaseModel):
    source: Literal["likes", "subscriptions", "playlist_items"]
    granularity: Literal["month", "quarter"]
    timestamp_source: str
    points: list[TrendPoint]
    excluded_without_timestamp: int


class DurationStats(BaseModel):
    source: Literal["likes", "playlist_items"]
    buckets: dict[str, int]
    mean_minutes: float | None
    median_minutes: float | None
    unknown_duration: int


class SubscriptionEntry(BaseModel):
    channel_id: str
    title: str | None
    subscribed_at: str | None


class PeriodComparison(BaseModel):
    source: Literal["likes", "subscriptions", "playlist_items"]
    timestamp_source: str
    period_count: int
    compare_count: int
    change_pct: float | None
    comparable: bool
    label: str


class PeriodOut(BaseModel):
    label: str
    start: str | None
    end: str | None


class AnalyzeEngagementResult(BaseModel):
    status: Literal["ok", "empty_account"]
    summary: str
    period: PeriodOut
    compare_to: PeriodOut | None
    totals: dict[str, int]
    top_channels: dict[str, list[CountShare]]
    top_categories: dict[str, list[CountShare]]
    subscriptions: list[SubscriptionEntry]
    trends: list[Trend]
    durations: list[DurationStats]
    comparison: list[PeriodComparison]
    notes: list[str]
    data_limits: list[str]
    quota_used: dict[str, int] = Field(default_factory=dict)
    writes_to_youtube: bool = False


class PlaylistItemOut(BaseModel):
    position: int
    video_id: str
    title: str | None
    channel_title: str | None
    duration_seconds: int
    duration_text: str
    url: str
    level: Literal["intro", "intermediate", "advanced"]


class ConstraintCheck(BaseModel):
    name: str
    satisfied: bool
    detail: str


class ProposePlaylistResult(BaseModel):
    status: Literal["proposed", "no_candidates"]
    summary: str
    proposal_id: str | None
    title: str
    privacy: PRIVACY
    items: list[PlaylistItemOut]
    total_duration_seconds: int
    target_duration_seconds: int
    fill_ratio: float
    constraints_checked: list[ConstraintCheck]
    excluded: dict[str, int]
    unknown_metadata: dict[str, int]
    unmet_constraints: list[str]
    shortfall_seconds: int
    estimated_write_quota: dict[str, int]
    ordering_note: str
    expires_at: str | None
    next_step: str
    quota_used: dict[str, int] = Field(default_factory=dict)
    writes_to_youtube: bool = False


class FailedItem(BaseModel):
    video_id: str
    code: str


class CreatePlaylistResult(BaseModel):
    status: Literal[
        "completed", "partial", "approval_pending", "declined", "cancelled", "timed_out", "already_completed"
    ]
    summary: str
    proposal_id: str
    approval_mechanism: Literal["elicitation", "local_code"] | None = None
    playlist_id: str | None = None
    playlist_url: str | None = None
    privacy: str | None = None
    items_inserted: int = 0
    items_total: int = 0
    items_failed: list[FailedItem] = Field(default_factory=list)
    quota_used: dict[str, int] = Field(default_factory=dict)
    expires_at: str | None = None
    next_step: str | None = None
    writes_to_youtube: bool = True


class AuthorizationResult(BaseModel):
    status: Literal["authorized", "revoked", "not_authorized"]
    summary: str
    scopes: list[str]
    cache_entries_deleted: int = 0
    writes_to_youtube: bool = False


class ClearCacheResult(BaseModel):
    status: Literal["cleared"]
    summary: str
    entries_deleted: int
    writes_to_youtube: bool = False
