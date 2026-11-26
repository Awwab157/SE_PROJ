"""FR-4: engagement analysis of likes, subscriptions and playlists, computed locally.

Every trend is labelled with the timestamp it uses. The API provides no like date, so like trends use
the *video publish date*; subscriptions use the subscription date; playlist items use the date the
item was added. Records without a timestamp are excluded from trends and counted.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from yt_intel_mcp.errors import InvalidInput, NotFound
from yt_intel_mcp.providers.base import pages_for
from yt_intel_mcp.schemas import (
    AnalyzeEngagementInput,
    AnalyzeEngagementResult,
    CountShare,
    DurationStats,
    PeriodComparison,
    PeriodOut,
    SubscriptionEntry,
    Trend,
    TrendPoint,
    VideoMeta,
    video_from_api,
)
from yt_intel_mcp.services import AppContext, run_metered, with_quota

TIMESTAMP_SOURCE = {
    "likes": "video publish date",
    "subscriptions": "subscription date",
    "playlist_items": "playlist-item added date",
}
DURATION_BUCKETS = ("<4 min", "4-20 min", "20-60 min", ">60 min")
LIKE_LIMIT_NOTE = "The YouTube API returns at most 1,000 liked videos; older likes are not included."


@dataclass(frozen=True)
class Period:
    label: str
    start: date | None
    end: date | None

    def contains(self, day: date | None) -> bool:
        if self.start is None:
            return True
        return day is not None and self.start <= day <= self.end

    @property
    def days(self) -> int | None:
        return None if self.start is None else (self.end - self.start).days + 1

    def out(self) -> PeriodOut:
        return PeriodOut(
            label=self.label,
            start=self.start.isoformat() if self.start else None,
            end=self.end.isoformat() if self.end else None,
        )


def _month_end(year: int, month: int) -> date:
    nxt = date(year + (month // 12), month % 12 + 1, 1)
    return nxt - timedelta(days=1)


def parse_period(value: str, today: date) -> Period:
    if value == "all":
        return Period("all", None, None)
    if m := re.fullmatch(r"last_(\d+)_days", value):
        n = max(1, int(m.group(1)))
        return Period(value, today - timedelta(days=n - 1), today)
    if re.fullmatch(r"\d{4}", value):
        y = int(value)
        return Period(value, date(y, 1, 1), date(y, 12, 31))
    if m := re.fullmatch(r"(\d{4})-Q([1-4])", value):
        y, q = int(m.group(1)), int(m.group(2))
        return Period(value, date(y, 3 * q - 2, 1), _month_end(y, 3 * q))
    if m := re.fullmatch(r"(\d{4})-(\d{2})", value):
        y, mo = int(m.group(1)), int(m.group(2))
        return Period(value, date(y, mo, 1), _month_end(y, mo))
    if m := re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})", value):
        start, end = date.fromisoformat(m.group(1)), date.fromisoformat(m.group(2))
        if end < start:
            raise ValueError("period end is before its start")
        return Period(value, start, end)
    raise ValueError(f"unsupported period: {value}")


def to_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def month_key(day: date) -> str:
    return f"{day.year}-{day.month:02d}"


def quarter_key(day: date) -> str:
    return f"{day.year}-Q{(day.month - 1) // 3 + 1}"


def duration_bucket(seconds: int) -> str:
    minutes = seconds / 60
    if minutes < 4:
        return "<4 min"
    if minutes <= 20:
        return "4-20 min"
    if minutes <= 60:
        return "20-60 min"
    return ">60 min"


def duration_stats(source: str, videos: list[VideoMeta]) -> DurationStats:
    known = [v.duration_seconds for v in videos if v.duration_seconds]
    buckets = {b: 0 for b in DURATION_BUCKETS}
    for s in known:
        buckets[duration_bucket(s)] += 1
    return DurationStats(
        source=source,
        buckets=buckets,
        mean_minutes=round(statistics.fmean(known) / 60, 2) if known else None,
        median_minutes=round(statistics.median(known) / 60, 2) if known else None,
        unknown_duration=len(videos) - len(known),
    )


def count_share(counter: Counter[str], labels: dict[str, str | None], top: int = 10) -> list[CountShare]:
    total = sum(counter.values())
    ranked = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:top]
    return [CountShare(key=k, label=labels.get(k), count=n, share=round(n / total, 4)) for k, n in ranked]


def trends(source: str, days: list[date | None]) -> list[Trend]:
    known = [d for d in days if d is not None]
    out = []
    for granularity, key in (("month", month_key), ("quarter", quarter_key)):
        counts = Counter(key(d) for d in known)
        out.append(
            Trend(
                source=source,
                granularity=granularity,
                timestamp_source=TIMESTAMP_SOURCE[source],
                points=[TrendPoint(period=k, count=counts[k]) for k in sorted(counts)],
                excluded_without_timestamp=len(days) - len(known),
            )
        )
    return out


def compare(source: str, days: list[date | None], period: Period, other: Period) -> PeriodComparison:
    a = sum(1 for d in days if d is not None and period.contains(d))
    b = sum(1 for d in days if d is not None and other.contains(d))
    reasons = []
    if period.days is None or other.days is None:
        reasons.append("'all' cannot be compared")
    elif abs(period.days - other.days) / max(period.days, other.days) > 0.1:
        reasons.append(f"different period lengths ({period.days} vs {other.days} days)")
    if a == 0 and b == 0:
        reasons.append("no records in either period")
    elif b == 0:
        reasons.append("no records in the comparison period")
    comparable = not reasons
    change = round((a - b) / b * 100, 1) if comparable else None
    label = (
        f"{a} vs {b} ({change:+.1f}%) by {TIMESTAMP_SOURCE[source]}"
        if comparable
        else "not comparable: " + "; ".join(reasons)
    )
    return PeriodComparison(
        source=source,
        timestamp_source=TIMESTAMP_SOURCE[source],
        period_count=a,
        compare_count=b,
        change_pct=change,
        comparable=comparable,
        label=label,
    )


def plan(app: AppContext) -> dict[str, int]:
    r = app.retrieval("engagement")
    item_pages = int(r["max_playlists"]) * pages_for(r["max_items_per_playlist"])
    return {
        "videos.list": pages_for(r["max_likes"])
        + pages_for(int(r["max_playlists"]) * int(r["max_items_per_playlist"])),
        "subscriptions.list": pages_for(r["max_subscriptions"]),
        "playlists.list": pages_for(r["max_playlists"]),
        "playlistItems.list": item_pages,
        "videoCategories.list": 1,
    }


def analyze_engagement(app: AppContext, inp: AnalyzeEngagementInput) -> AnalyzeEngagementResult:
    today = app.clock.now().date()
    try:
        period = parse_period(inp.period, today)
        other = parse_period(inp.compare_to, today) if inp.compare_to else None
    except ValueError as exc:
        raise InvalidInput(f"Invalid period: {exc}.") from exc
    r = app.retrieval("engagement")

    def work() -> AnalyzeEngagementResult:
        p = app.provider
        liked = [video_from_api(v) for v in p.list_liked_videos(int(r["max_likes"]))]
        subs = p.list_subscriptions(int(r["max_subscriptions"]))
        playlists = p.list_playlists(int(r["max_playlists"]))
        items: list[dict[str, Any]] = []
        for pl in playlists[: int(r["max_playlists"])]:
            try:
                items.extend(p.list_playlist_items(pl["playlist_id"], int(r["max_items_per_playlist"])))
            except NotFound:
                continue
        data_limits = [LIKE_LIMIT_NOTE] if len(liked) >= 1000 else []
        data_limits.append(
            "YouTube does not provide the date a video was liked; like trends use the video publish date."
        )
        if not liked and not subs and not items:
            return AnalyzeEngagementResult(
                status="empty_account",
                summary="This account has no likes, subscriptions or playlist items to analyse.",
                period=period.out(),
                compare_to=other.out() if other else None,
                totals={},
                top_channels={},
                top_categories={},
                subscriptions=[],
                trends=[],
                durations=[],
                comparison=[],
                notes=[],
                data_limits=data_limits,
            )
        item_ids = list(dict.fromkeys(i["video_id"] for i in items if i.get("video_id")))
        item_videos = {v["id"]: video_from_api(v) for v in p.get_videos(item_ids)} if item_ids else {}
        categories = p.list_video_categories(str(r.get("category_region", "US")))

        like_days = [to_date(v.published_at) for v in liked]
        sub_days = [to_date(s.get("subscribed_at")) for s in subs]
        item_days = [to_date(i.get("added_at")) for i in items]

        liked_in = [v for v, d in zip(liked, like_days, strict=True) if period.contains(d)]
        items_in = [i for i, d in zip(items, item_days, strict=True) if period.contains(d)]
        item_videos_in = [item_videos[i["video_id"]] for i in items_in if i.get("video_id") in item_videos]
        subs_in = [s for s, d in zip(subs, sub_days, strict=True) if period.contains(d)]

        channel_labels: dict[str, str | None] = {}
        for v in [*liked, *item_videos.values()]:
            if v.channel_id:
                channel_labels.setdefault(v.channel_id, v.channel_title)
        top_channels = {
            "likes": count_share(Counter(v.channel_id for v in liked_in if v.channel_id), channel_labels),
            "playlist_items": count_share(
                Counter(v.channel_id for v in item_videos_in if v.channel_id), channel_labels
            ),
        }
        top_categories = {
            "likes": count_share(Counter(v.category_id for v in liked_in if v.category_id), categories),
            "playlist_items": count_share(Counter(v.category_id for v in item_videos_in if v.category_id), categories),
        }
        subscriptions = sorted(
            (
                SubscriptionEntry(
                    channel_id=s["channel_id"], title=s.get("title"), subscribed_at=s.get("subscribed_at")
                )
                for s in subs_in
            ),
            key=lambda e: (e.subscribed_at or "", e.channel_id),
            reverse=True,
        )

        def in_period(days: list[date | None]) -> list[date | None]:
            # Dated records inside the period, plus undated records (counted as excluded by trends()).
            return [d for d in days if d is None or period.contains(d)]

        trend_list = [
            *trends("likes", in_period(like_days)),
            *trends("subscriptions", in_period(sub_days)),
            *trends("playlist_items", in_period(item_days)),
        ]
        comparison = []
        if other is not None:
            comparison = [
                compare("likes", like_days, period, other),
                compare("subscriptions", sub_days, period, other),
                compare("playlist_items", item_days, period, other),
            ]
        missing = {
            "likes": sum(1 for d in like_days if d is None),
            "subscriptions": sum(1 for d in sub_days if d is None),
            "playlist_items": sum(1 for d in item_days if d is None),
        }
        notes = [
            "Analysis covers likes, subscriptions and playlists only.",
            "Trends: likes by video publish date, subscriptions by subscription date, playlist items by the "
            "date they were added.",
        ]
        if any(missing.values()):
            notes.append(
                "Records without a timestamp were excluded from trends: "
                + ", ".join(f"{k}: {v}" for k, v in missing.items() if v)
                + "."
            )
        totals = {"likes": len(liked_in), "subscriptions": len(subs_in), "playlist_items": len(items_in)}
        return AnalyzeEngagementResult(
            status="ok",
            summary=(
                f"Period {period.label}: {totals['likes']} likes, {totals['subscriptions']} subscriptions and "
                f"{totals['playlist_items']} playlist items analysed."
            ),
            period=period.out(),
            compare_to=other.out() if other else None,
            totals=totals,
            top_channels=top_channels,
            top_categories=top_categories,
            subscriptions=subscriptions,
            trends=trend_list,
            durations=[duration_stats("likes", liked_in), duration_stats("playlist_items", item_videos_in)],
            comparison=comparison,
            notes=notes,
            data_limits=data_limits,
        )

    result, used = run_metered(app, "analyze_engagement", plan(app), work)
    return with_quota(result, used)
