"""TQ-2: services against the fixture provider."""

import pytest

from tests.conftest import CH, consume
from yt_intel_mcp.errors import NotFound
from yt_intel_mcp.schemas import (
    FindSimilarChannelsInput,
    FindSimilarVideosInput,
    RecommendFilters,
    RecommendVideosInput,
)
from yt_intel_mcp.services import recommendations, similar_channels, similar_videos
from yt_intel_mcp.services.similar_videos import STOPPED_NOTE


def sv(app, video, limit=10):
    return similar_videos.find_similar_videos(app, FindSimilarVideosInput(video=video, limit=limit))


def sc(app, channel, limit=10):
    return similar_channels.find_similar_channels(app, FindSimilarChannelsInput(channel=channel, limit=limit))


# --- FR-1 ---------------------------------------------------------------------------------------------


def test_similar_videos_excludes_seed_private_deleted(app, provider) -> None:
    res = sv(app, "https://www.youtube.com/watch?v=pdIntro0001", limit=50)
    ids = [r.video_id for r in res.results]
    assert res.status == "ok"
    assert "pdIntro0001" not in ids
    assert "pyPriv00016" not in ids and "pyProc00018" not in ids and "deletedVid1" not in ids
    assert res.excluded["deleted_or_private"] == 1
    assert res.excluded["private_or_unavailable"] == 2
    assert res.results == sorted(res.results, key=lambda r: (-r.score, r.video_id))
    assert all(r.explanation for r in res.results)
    assert provider.write_calls == []
    assert res.quota_used["search_calls"] == provider.count("search_videos")


def test_missing_seed_fields_reported_unavailable(app) -> None:
    res = sv(app, "pyNoTags015")
    assert res.status == "ok"
    assert "tags" in res.seed.unavailable_fields
    assert any("no tags" in n for n in res.notes)


def test_seed_without_language_reported(app) -> None:
    assert "language" in sv(app, "pyNoLang017").seed.unavailable_fields


def test_insufficient_metadata(app, provider) -> None:
    res = sv(app, "noMeta00019")
    assert res.status == "insufficient_metadata"
    assert res.results == []
    assert provider.count("search_videos") == 0


def test_unknown_and_private_seed(app) -> None:
    with pytest.raises(NotFound):
        sv(app, "zzzzzzzzzzz")
    with pytest.raises(NotFound):
        sv(app, "pyPriv00016")


def test_candidate_retrieval_stops_at_quota_limit(app, provider) -> None:
    consume(app, search_calls=99)  # only one search call left today
    res = sv(app, "pdIntro0001")
    assert provider.count("search_videos") == 1
    assert [m for m, _ in provider.calls][:2] == ["get_videos", "search_videos"]
    assert STOPPED_NOTE in res.notes
    assert res.status == "ok"
    assert app.quota.status()["buckets"]["search_calls"]["remaining"] == 0


# --- FR-2 ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ref",
    [
        CH["dd"],
        "@datadojo",
        f"https://www.youtube.com/channel/{CH['dd']}",
        "https://www.youtube.com/@datadojo",
        "https://www.youtube.com/user/datadojo",
    ],
)
def test_channel_resolution_forms(app, ref) -> None:
    res = sc(app, ref)
    assert res.status == "ok"
    assert res.seed.channel_id == CH["dd"]
    assert CH["dd"] not in [r.channel_id for r in res.results]
    assert res.results[0].channel_id == CH["pp"]  # the other pandas channel


def test_custom_url_single_match(app) -> None:
    res = sc(app, "https://www.youtube.com/c/nightskynotes")
    assert res.status == "ok"
    assert res.seed.channel_id == CH["ns"]


def test_custom_url_ambiguous_returns_candidates(app) -> None:
    res = sc(app, "https://www.youtube.com/c/breadlab")
    assert res.status == "ambiguous_channel"
    assert {c.channel_id for c in res.candidates} == {CH["cl"], CH["bt"]}
    assert res.results == []


def test_channel_not_found_or_terminated(app) -> None:
    with pytest.raises(NotFound):
        sc(app, "@nobodyhere")
    with pytest.raises(NotFound):
        sc(app, CH["gone"])


def test_hidden_subscriber_count_not_shown(app) -> None:
    res = sc(app, "@crumblab")
    bake = next(r for r in res.results if r.channel_id == CH["bt"])
    assert bake.subscriber_count is None


def test_channel_results_ordered_by_content(app) -> None:
    res = sc(app, "@datadojo")
    scores = [r.score for r in res.results]
    assert scores == sorted(scores, reverse=True)


# --- FR-3 ---------------------------------------------------------------------------------------------


def test_recommendations_profile_and_exclusions(app, provider) -> None:
    res = recommendations.recommend_videos(app, RecommendVideosInput(limit=50))
    assert res.status == "ok"
    ids = {r.video_id for r in res.results}
    liked = set(provider.liked_ids)
    in_playlists = {i["video_id"] for p in provider.playlists for i in p["items"]}
    assert not ids & liked
    assert not ids & in_playlists
    assert res.excluded["already_liked_or_in_playlist"] > 0
    assert res.profile.signal_counts == {"likes": 8, "subscriptions": 4, "playlist_items": 5}
    assert "pandas" in res.profile.top_terms
    assert all(r.signals for r in res.results)
    assert "watch" not in " ".join(res.notes + res.data_limits).lower()
    assert all(not write for write in app.authorizer.credential_requests)


def test_recommendation_filters(app) -> None:
    res = recommendations.recommend_videos(
        app, RecommendVideosInput(limit=50, filters=RecommendFilters(max_duration_min=15, language="en"))
    )
    assert all(r.duration_seconds is not None and r.duration_seconds <= 900 for r in res.results)
    assert all(r.language == "en" for r in res.results)
