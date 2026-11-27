"""FR-1: find videos similar to a seed video, from public metadata only."""

from __future__ import annotations

from typing import Any

from yt_intel_mcp import quota
from yt_intel_mcp.errors import NotFound
from yt_intel_mcp.ids import parse_video_id
from yt_intel_mcp.providers.base import pages_for
from yt_intel_mcp.schemas import (
    SEED_DESCRIPTION_CHARS,
    FindSimilarVideosInput,
    FindSimilarVideosResult,
    SeedVideo,
    SimilarVideo,
    VideoMeta,
    summary_of,
    video_from_api,
)
from yt_intel_mcp.services import AppContext, run_metered, with_quota
from yt_intel_mcp.similarity import has_text, keyword_terms, score_videos, video_document

STOPPED_NOTE = "Candidate retrieval stopped early because the reserved quota for this request was used up."


def plan(app: AppContext) -> tuple[dict[str, int], dict[str, int]]:
    r = app.retrieval("similar_videos")
    detail_calls = pages_for(r["max_candidates"])
    full = {
        "videos.list": 1 + detail_calls,
        "search.list": r["max_search_queries"],
        "channels.list": 1,
        "playlistItems.list": pages_for(r["seed_channel_uploads"]),
    }
    minimum = {"videos.list": 1 + detail_calls, "search.list": 1}
    return full, minimum


def build_queries(seed: VideoMeta, terms: list[str], max_queries: int) -> list[tuple[str, dict[str, Any]]]:
    base: dict[str, Any] = {"relevanceLanguage": seed.language} if seed.language else {}
    queries: list[tuple[str, dict[str, Any]]] = []
    if terms:
        queries.append((" ".join(terms[:4]), dict(base)))
    if seed.tags:
        queries.append((" ".join(seed.tags[:3]), dict(base)))
    if seed.category_id and terms:
        queries.append((" ".join(terms[:2]), {**base, "videoCategoryId": seed.category_id}))
    if seed.title:
        queries.append((seed.title[:80], dict(base)))
    unique: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for q, f in queries:
        key = q.lower() + repr(sorted(f.items()))
        if q.strip() and key not in seen:
            seen.add(key)
            unique.append((q, f))
    return unique[:max_queries]


def find_similar_videos(app: AppContext, inp: FindSimilarVideosInput) -> FindSimilarVideosResult:
    video_id = parse_video_id(inp.video)
    limits = app.similarity.get("limits", {})
    limit = min(inp.limit, int(limits.get("max_limit", 50)))
    r = app.retrieval("similar_videos")
    weights = app.similarity["video_weights"]
    full, minimum = plan(app)
    detail_calls = pages_for(r["max_candidates"])

    def work() -> FindSimilarVideosResult:
        items = app.provider.get_videos([video_id])
        if not items:
            raise NotFound("The video was not found. It may be private, deleted or the ID may be wrong.")
        seed = video_from_api(items[0])
        if not seed.available:
            raise NotFound("The video is private or not available.")
        seed_out = SeedVideo(
            video_id=seed.video_id,
            title=seed.title,
            channel_id=seed.channel_id,
            channel_title=seed.channel_title,
            url=seed.url,
            description=(seed.description or "")[:SEED_DESCRIPTION_CHARS] or None,
            tags=seed.tags[:20],
            duration_seconds=seed.duration_seconds,
            category_id=seed.category_id,
            language=seed.language,
            published_at=seed.published_at,
            unavailable_fields=seed.unavailable_fields,
        )
        notes: list[str] = []
        if seed.unavailable_fields:
            notes.append("Seed metadata unavailable: " + ", ".join(seed.unavailable_fields) + ".")
        if not has_text(video_document(seed)):
            return FindSimilarVideosResult(
                status="insufficient_metadata",
                summary="The video has no usable title, description or tags, so similar videos cannot be found.",
                seed=seed_out,
                results=[],
                excluded={},
                notes=notes,
            )
        if not seed.tags:
            notes.append("The video has no tags; similarity uses its title and description.")

        terms = keyword_terms(seed.title, seed.tags, seed.description, int(r["query_terms"]))
        keep = {"videos.list": detail_calls}
        candidate_ids: dict[str, None] = {}
        stopped = False
        for query, filters in build_queries(seed, terms, int(r["max_search_queries"])):
            if not quota.can_afford("search.list", keep=keep):
                stopped = True
                break
            resp = app.provider.search_videos(query, {**filters, "maxResults": int(r["results_per_search"])})
            for item in resp.get("items", []):
                candidate_ids.setdefault(item["video_id"], None)
        if seed.channel_id:
            if quota.can_afford("channels.list", keep=keep) and quota.can_afford(
                "playlistItems.list", count=pages_for(r["seed_channel_uploads"]), keep=keep
            ):
                try:
                    for item in app.provider.list_channel_uploads(seed.channel_id, int(r["seed_channel_uploads"])):
                        candidate_ids.setdefault(item["video_id"], None)
                except NotFound:
                    notes.append("The seed channel's uploads could not be listed.")
            else:
                stopped = True
        candidate_ids.pop(seed.video_id, None)
        ids = list(candidate_ids)[: int(r["max_candidates"])]

        raw: list[dict[str, Any]] = []
        for start in range(0, len(ids), 50):
            if not quota.can_afford("videos.list"):
                stopped = True
                break
            raw.extend(app.provider.get_videos(ids[start : start + 50]))
        if stopped:
            notes.append(STOPPED_NOTE)

        returned = {item["id"] for item in raw}
        metas = [video_from_api(item) for item in raw]
        excluded = {
            "deleted_or_private": len([i for i in ids if i not in returned]),
            "private_or_unavailable": sum(1 for m in metas if not m.available),
        }
        candidates = [m for m in metas if m.available]
        scored = score_videos(seed, candidates, weights)[:limit]
        results = [
            SimilarVideo(**summary_of(s.video), score=s.score, components=s.components, explanation=s.explanation)
            for s in scored
        ]
        if not results:
            return FindSimilarVideosResult(
                status="no_candidates",
                summary="No similar public videos were found for this video.",
                seed=seed_out,
                results=[],
                excluded=excluded,
                notes=notes,
            )
        top = results[0]
        return FindSimilarVideosResult(
            status="ok",
            summary=(
                f"Found {len(results)} videos similar to the seed video (from {len(candidates)} candidates). "
                f'Top match: "{top.title}" (score {top.score:.2f}).'
            ),
            seed=seed_out,
            results=results,
            excluded=excluded,
            notes=notes,
        )

    result, used = run_metered(app, "find_similar_videos", full, work, min_plan=minimum)
    return with_quota(result, used)
