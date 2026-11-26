"""FR-2: find channels similar to a seed channel, ranked by content similarity."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from yt_intel_mcp import quota
from yt_intel_mcp.errors import NotFound
from yt_intel_mcp.ids import ChannelRef, channel_url, parse_channel_ref
from yt_intel_mcp.providers.base import pages_for
from yt_intel_mcp.schemas import (
    ChannelMeta,
    ChannelRefOut,
    FindSimilarChannelsInput,
    FindSimilarChannelsResult,
    SimilarChannel,
    channel_from_api,
    video_from_api,
)
from yt_intel_mcp.services import AppContext, run_metered, with_quota
from yt_intel_mcp.similarity import ChannelProfile, has_text, keyword_terms, rank_channels

NOT_FOUND = "The channel was not found. It may be invalid, terminated or the URL may be wrong."


def plan(app: AppContext, ref: ChannelRef) -> tuple[dict[str, int], dict[str, int]]:
    r = app.retrieval("similar_channels")
    custom = 1 if ref.kind == "custom" else 0
    profiles = int(r["max_candidate_profiles"])
    full = {
        "search.list": int(r["max_search_queries"]) + custom,
        "channels.list": 1 + 1 + 1 + profiles,
        "playlistItems.list": pages_for(r["seed_uploads"]) + profiles * pages_for(r["candidate_uploads"]),
        "videos.list": 1,
    }
    minimum = {"search.list": 1 + custom, "channels.list": 3, "playlistItems.list": 1, "videos.list": 1}
    return full, minimum


def uploads_per_30_days(dates: list[str | None]) -> float | None:
    parsed = []
    for d in dates:
        try:
            parsed.append(datetime.fromisoformat((d or "").replace("Z", "+00:00")))
        except ValueError:
            continue
    if len(parsed) < 2:
        return None
    span_days = max(1.0, (max(parsed) - min(parsed)).total_seconds() / 86400)
    return round(len(parsed) / span_days * 30, 3)


def _ref_out(meta: ChannelMeta) -> ChannelRefOut:
    return ChannelRefOut(channel_id=meta.channel_id, title=meta.title, url=channel_url(meta.channel_id))


def _profile_document(meta: ChannelMeta, uploads: list[dict[str, Any]], tags: list[str]) -> str:
    parts = [meta.title or "", meta.title or "", meta.description or ""]
    for u in uploads:
        parts.append(u.get("title") or "")
        parts.append((u.get("description") or "")[:500])
    parts.append(" ".join(tags))
    return " ".join(parts)


def find_similar_channels(app: AppContext, inp: FindSimilarChannelsInput) -> FindSimilarChannelsResult:
    ref = parse_channel_ref(inp.channel)
    limit = min(inp.limit, int(app.similarity.get("limits", {}).get("max_limit", 50)))
    r = app.retrieval("similar_channels")
    cfg = app.similarity["channel"]
    full, minimum = plan(app, ref)

    def resolve() -> tuple[dict[str, Any] | None, list[ChannelRefOut]]:
        p = app.provider
        if ref.kind == "id":
            items = p.get_channels(ids=[ref.value])
        elif ref.kind == "handle":
            items = p.get_channels(for_handle=ref.value)
        elif ref.kind == "username":
            items = p.get_channels(for_username=ref.value)
        else:  # /c/ custom URL: channel-only search, never auto-pick between several matches
            found = p.search_channels(ref.value, max_results=10)
            if len(found) > 1:
                return None, [
                    ChannelRefOut(channel_id=f["channel_id"], title=f.get("title"), url=channel_url(f["channel_id"]))
                    for f in found
                ]
            items = p.get_channels(ids=[found[0]["channel_id"]]) if found else []
        if not items:
            raise NotFound(NOT_FOUND)
        return items[0], []

    def work() -> FindSimilarChannelsResult:
        seed_item, ambiguous = resolve()
        if seed_item is None:
            return FindSimilarChannelsResult(
                status="ambiguous_channel",
                summary=(
                    f"The /c/ URL matches {len(ambiguous)} channels. Ask the user which one they mean and "
                    "call again with its channel ID or @handle."
                ),
                seed=None,
                results=[],
                candidates=ambiguous,
                notes=[],
            )
        seed = channel_from_api(seed_item)
        notes: list[str] = []
        try:
            uploads = app.provider.list_channel_uploads(seed.channel_id, int(r["seed_uploads"]))
        except NotFound as exc:
            raise NotFound(NOT_FOUND) from exc
        upload_videos = [video_from_api(v) for v in app.provider.get_videos([u["video_id"] for u in uploads][:50])]
        tags = [t for v in upload_videos for t in v.tags]
        document = _profile_document(seed, uploads, tags)
        if not has_text(document):
            return FindSimilarChannelsResult(
                status="insufficient_metadata",
                summary="The channel has no usable title, description or upload metadata to compare.",
                seed=_ref_out(seed),
                results=[],
                notes=notes,
            )
        upload_titles = " ".join(u.get("title") or "" for u in uploads)
        terms = keyword_terms(f"{seed.title or ''} {upload_titles}", tags, seed.description, 6)
        queries = [" ".join(terms[i : i + 3]) for i in range(0, len(terms), 3) if terms[i : i + 3]]
        queries = queries[: int(r["max_search_queries"])] or [seed.title or ""]

        keep = {"channels.list": 1}
        candidate_ids: dict[str, None] = {}
        for query in queries:
            if not quota.can_afford("search.list", keep=keep):
                notes.append("Candidate search stopped because the reserved quota was used up.")
                break
            for found in app.provider.search_channels(query, max_results=int(r["results_per_search"])):
                if found["channel_id"] != seed.channel_id:
                    candidate_ids.setdefault(found["channel_id"], None)
        ids = list(candidate_ids)[:50]
        details = [channel_from_api(c) for c in app.provider.get_channels(ids=ids)] if ids else []
        by_id = {d.channel_id: d for d in details}

        seed_profile = ChannelProfile(
            seed.channel_id,
            seed.title,
            document,
            seed.subscriber_count,
            uploads_per_30_days([u.get("published_at") for u in uploads]),
            seed.language,
        )
        profiles: list[ChannelProfile] = []
        for index, cid in enumerate(i for i in ids if i in by_id):
            meta = by_id[cid]
            cand_uploads: list[dict[str, Any]] = []
            if (
                index < int(r["max_candidate_profiles"])
                and quota.can_afford("channels.list")
                and quota.can_afford("playlistItems.list", count=pages_for(r["candidate_uploads"]))
            ):
                try:
                    cand_uploads = app.provider.list_channel_uploads(cid, int(r["candidate_uploads"]))
                except NotFound:
                    cand_uploads = []
            profiles.append(
                ChannelProfile(
                    cid,
                    meta.title,
                    _profile_document(meta, cand_uploads, []),
                    meta.subscriber_count,
                    uploads_per_30_days([u.get("published_at") for u in cand_uploads]),
                    meta.language,
                )
            )
        ranked = rank_channels(
            seed_profile, profiles, cfg.get("secondary_weights", {}), int(cfg.get("content_precision", 3))
        )[:limit]
        results = [
            SimilarChannel(
                channel_id=s.profile.channel_id,
                title=s.profile.title,
                url=channel_url(s.profile.channel_id),
                subscriber_count=by_id[s.profile.channel_id].subscriber_count,
                score=s.score,
                secondary_score=s.secondary_score,
                explanation=s.explanation,
            )
            for s in ranked
        ]
        if not results:
            return FindSimilarChannelsResult(
                status="no_candidates",
                summary="No similar channels were found.",
                seed=_ref_out(seed),
                results=[],
                notes=notes,
            )
        notes.append("Ranking is by content similarity; subscriber count, upload cadence and language only break ties.")
        return FindSimilarChannelsResult(
            status="ok",
            summary=f'Found {len(results)} channels similar to "{seed.title}". Top match: "{results[0].title}".',
            seed=_ref_out(seed),
            results=results,
            notes=notes,
        )

    result, used = run_metered(app, "find_similar_channels", full, work, min_plan=minimum)
    return with_quota(result, used)
