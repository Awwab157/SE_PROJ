"""FR-3: recommendations from the user's likes, subscriptions and playlists (read scope only).

The YouTube Data API does not expose viewing activity, so none is used or claimed (FR-3.7).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from yt_intel_mcp import quota
from yt_intel_mcp.errors import NotFound
from yt_intel_mcp.providers.base import pages_for
from yt_intel_mcp.schemas import (
    InterestProfile,
    Recommendation,
    RecommendVideosInput,
    RecommendVideosResult,
    VideoMeta,
    summary_of,
    video_from_api,
)
from yt_intel_mcp.services import AppContext, run_metered, with_quota
from yt_intel_mcp.similarity import tfidf_cosines, tokens, video_document

BASIS_NOTE = "Recommendations are based only on your likes, subscriptions and playlists."
LIKE_LIMIT_NOTE = "The YouTube API returns at most 1,000 liked videos, so older likes were not included in the profile."
SCORE_WEIGHTS = {"text": 0.6, "liked_channel": 0.2, "subscribed": 0.1, "category": 0.1}


def plan(app: AppContext) -> tuple[dict[str, int], dict[str, int]]:
    r = app.retrieval("recommendations")
    reads = {
        "videos.list": pages_for(r["max_likes"]),
        "subscriptions.list": pages_for(r["max_subscriptions"]),
        "playlists.list": pages_for(r["max_playlists"]),
        "playlistItems.list": int(r["max_playlists"]) * pages_for(r["max_items_per_playlist"]),
    }
    detail = pages_for(
        int(r["max_search_queries"]) * int(r["results_per_search"])
        + int(r["subscribed_channels_sampled"]) * int(r["uploads_per_channel"])
    )
    sampled = int(r["subscribed_channels_sampled"])
    full = {
        **reads,
        "videos.list": reads["videos.list"] + detail,
        "search.list": int(r["max_search_queries"]),
        "channels.list": sampled,
        "playlistItems.list": reads["playlistItems.list"] + sampled * pages_for(r["uploads_per_channel"]),
    }
    minimum = {**reads, "videos.list": reads["videos.list"] + detail, "search.list": 1}
    return full, minimum


def _duration_filter(max_seconds: float | None) -> str | None:
    if max_seconds is not None and max_seconds < 240:
        return "short"
    return None


def recommend_videos(app: AppContext, inp: RecommendVideosInput) -> RecommendVideosResult:
    r = app.retrieval("recommendations")
    limit = min(inp.limit, int(app.similarity.get("limits", {}).get("max_limit", 50)))
    f = inp.filters
    max_seconds = f.max_duration_min * 60 if f.max_duration_min else None
    full, minimum = plan(app)

    def work() -> RecommendVideosResult:
        p = app.provider
        liked = [video_from_api(v) for v in p.list_liked_videos(int(r["max_likes"]))]
        like_limit_reached = len(liked) >= 1000
        subs = p.list_subscriptions(int(r["max_subscriptions"]))
        playlists = p.list_playlists(int(r["max_playlists"]))
        playlist_items: list[dict[str, Any]] = []
        for pl in playlists[: int(r["max_playlists"])]:
            try:
                playlist_items.extend(p.list_playlist_items(pl["playlist_id"], int(r["max_items_per_playlist"])))
            except NotFound:
                continue
        data_limits = [LIKE_LIMIT_NOTE] if like_limit_reached else []
        if not liked and not subs and not playlist_items:
            return RecommendVideosResult(
                status="empty_account",
                summary=(
                    "This account has no likes, subscriptions or playlist items yet, so there is nothing to "
                    "base recommendations on. Like some videos or subscribe to channels and try again."
                ),
                results=[],
                profile=None,
                excluded={},
                notes=[BASIS_NOTE],
                data_limits=data_limits,
            )

        # --- interest profile ---------------------------------------------------------------------
        term_weights: Counter[str] = Counter()
        for v in liked:
            for t in tokens(v.title):
                term_weights[t] += 3
            for t in tokens(" ".join(v.tags)):
                term_weights[t] += 2
        for item in playlist_items:
            for t in tokens(item.get("title")):
                term_weights[t] += 2
        for s in subs:
            for t in tokens(s.get("title")):
                term_weights[t] += 1
        top_terms = [t for t, _ in sorted(term_weights.items(), key=lambda kv: (-kv[1], kv[0]))[:12]]
        liked_channels = Counter(v.channel_id for v in liked if v.channel_id)
        subscribed = {s["channel_id"] for s in subs if s.get("channel_id")}
        categories = Counter(v.category_id for v in liked if v.category_id)
        top_categories = [c for c, _ in sorted(categories.items(), key=lambda kv: (-kv[1], kv[0]))[:3]]
        profile = InterestProfile(
            top_terms=top_terms,
            top_channels=[c for c, _ in sorted(liked_channels.items(), key=lambda kv: (-kv[1], kv[0]))[:5]],
            top_categories=top_categories,
            signal_counts={
                "likes": len(liked),
                "subscriptions": len(subs),
                "playlist_items": len(playlist_items),
            },
        )
        exclude = {v.video_id for v in liked} | {i["video_id"] for i in playlist_items if i.get("video_id")}

        # --- candidates ---------------------------------------------------------------------------
        filters: dict[str, Any] = {"maxResults": int(r["results_per_search"])}
        if f.language:
            filters["relevanceLanguage"] = f.language
        if f.category:
            filters["videoCategoryId"] = f.category
        if _duration_filter(max_seconds):
            filters["videoDuration"] = _duration_filter(max_seconds)
        queries = [" ".join(top_terms[i : i + 2]) for i in range(0, min(len(top_terms), 6), 2)]
        detail_calls = full["videos.list"] - pages_for(r["max_likes"])
        keep = {"videos.list": detail_calls}
        notes = [BASIS_NOTE]
        candidate_ids: dict[str, str] = {}
        for query in queries[: int(r["max_search_queries"])]:
            if not quota.can_afford("search.list", keep=keep):
                notes.append("Candidate search stopped because the reserved quota was used up.")
                break
            for item in p.search_videos(query, filters).get("items", []):
                candidate_ids.setdefault(item["video_id"], "search")
        sampled = sorted(subscribed, key=lambda c: (-liked_channels.get(c, 0), c))[
            : int(r["subscribed_channels_sampled"])
        ]
        for channel_id in sampled:
            if not (
                quota.can_afford("channels.list", keep=keep)
                and quota.can_afford("playlistItems.list", count=pages_for(r["uploads_per_channel"]), keep=keep)
            ):
                break
            try:
                for item in p.list_channel_uploads(channel_id, int(r["uploads_per_channel"])):
                    candidate_ids.setdefault(item["video_id"], "subscription")
            except NotFound:
                continue
        excluded: Counter[str] = Counter()
        ids = []
        for vid in candidate_ids:
            if vid in exclude:
                excluded["already_liked_or_in_playlist"] += 1
            else:
                ids.append(vid)
        raw: list[dict[str, Any]] = []
        for start in range(0, len(ids), 50):
            if not quota.can_afford("videos.list"):
                notes.append("Candidate details stopped because the reserved quota was used up.")
                break
            raw.extend(p.get_videos(ids[start : start + 50]))
        excluded["deleted_or_private"] += len(ids) - len(raw)
        candidates: list[VideoMeta] = []
        for v in (video_from_api(x) for x in raw):
            if not v.available:
                excluded["private_or_unavailable"] += 1
            elif max_seconds is not None and v.duration_seconds is None:
                excluded["unknown_duration"] += 1
            elif max_seconds is not None and v.duration_seconds > max_seconds:
                excluded["longer_than_max_duration"] += 1
            elif f.language and v.language is None:
                excluded["unknown_language"] += 1
            elif f.language and v.language != f.language:
                excluded["language_mismatch"] += 1
            elif f.category and v.category_id != f.category:
                excluded["category_mismatch"] += 1
            else:
                candidates.append(v)

        if not candidates:
            return RecommendVideosResult(
                status="no_candidates",
                summary="No new videos matching your interests and filters were found.",
                results=[],
                profile=profile,
                excluded=dict(excluded),
                notes=notes,
                data_limits=data_limits,
            )

        profile_doc = " ".join(t for t, w in term_weights.most_common(50) for _ in range(min(w, 5)))
        cosines, shared = tfidf_cosines(profile_doc, [video_document(c) for c in candidates])
        recs: list[Recommendation] = []
        for cand, cos, terms in zip(candidates, cosines, shared, strict=True):
            liked_n = liked_channels.get(cand.channel_id or "", 0)
            parts = {
                "text": cos,
                "liked_channel": min(1.0, liked_n / 3),
                "subscribed": 1.0 if cand.channel_id in subscribed else 0.0,
                "category": 1.0 if cand.category_id in top_categories else 0.0,
            }
            score = round(sum(SCORE_WEIGHTS[k] * v for k, v in parts.items()), 4)
            signals = []
            if terms:
                signals.append("matches topics from your likes and playlists: " + ", ".join(terms))
            if liked_n:
                signals.append(f"from a channel whose videos you liked ({liked_n})")
            if parts["subscribed"]:
                signals.append("from a channel you subscribe to")
            if parts["category"]:
                signals.append(f"in a category you often like (category {cand.category_id})")
            if not signals:
                signals.append("found by searching your top interest terms")
            recs.append(Recommendation(**summary_of(cand), score=score, signals=signals))
        recs.sort(key=lambda x: (-x.score, x.video_id))
        recs = recs[:limit]
        return RecommendVideosResult(
            status="ok",
            summary=(
                f"{len(recs)} recommendations based on {len(liked)} likes, {len(subs)} subscriptions and "
                f'{len(playlist_items)} playlist items. Top: "{recs[0].title}".'
            ),
            results=recs,
            profile=profile,
            excluded=dict(excluded),
            notes=notes,
            data_limits=data_limits,
        )

    result, used = run_metered(app, "recommend_videos", full, work, min_plan=minimum)
    return with_quota(result, used)
