from yt_intel_mcp.schemas import ProposePlaylistInput, VideoMeta
from yt_intel_mcp.services import playlist
from yt_intel_mcp.services.playlist import Candidate, level_of, order_intro_to_advanced, select_videos


def cands(durations: list[int]) -> list[Candidate]:
    return [
        Candidate(VideoMeta(video_id=f"v{i:010d}", title=f"t{i}", duration_seconds=d, language="en"), i)
        for i, d in enumerate(durations)
    ]


def total(sel) -> int:
    return sum(c.seconds for c in sel)


def test_never_exceeds_total() -> None:
    for target in (600, 1000, 3600, 5400):
        sel = select_videos(cands([700, 650, 400, 333, 299, 120, 61, 59]), target)
        assert total(sel) <= target


def test_greedy_when_it_reaches_90_percent() -> None:
    sel = select_videos(cands([500, 400, 100]), 1000)
    assert total(sel) == 1000
    assert [c.rank for c in sel] == [0, 1, 2]


def test_subset_sum_improves_on_greedy() -> None:
    # Greedy takes 600 (rank 0) then nothing fits: 60%. 500 + 500 = 100%.
    sel = select_videos(cands([600, 500, 500]), 1000)
    assert total(sel) >= 900
    assert total(sel) <= 1000


def test_infeasible_returns_closest() -> None:
    sel = select_videos(cands([300, 200]), 3600)
    assert total(sel) == 500


def test_max_items_respected() -> None:
    sel = select_videos(cands([10] * 30), 3600, max_items=5)
    assert len(sel) <= 5


def test_relevance_order_preserved() -> None:
    sel = select_videos(cands([100, 100, 100, 100]), 300)
    assert [c.rank for c in sel] == [0, 1, 2]


def test_levels_and_ordering() -> None:
    assert level_of("Pandas for Beginners: Introduction") == "intro"
    assert level_of("Advanced pandas deep dive") == "advanced"
    assert level_of("Merging DataFrames") == "intermediate"
    items = [
        Candidate(VideoMeta(video_id="a" * 11, title="Advanced tricks", duration_seconds=10), 0),
        Candidate(VideoMeta(video_id="b" * 11, title="Merging", duration_seconds=10), 1),
        Candidate(VideoMeta(video_id="c" * 11, title="Introduction", duration_seconds=10), 2),
    ]
    assert [c.video.title for c in order_intro_to_advanced(items)] == ["Introduction", "Merging", "Advanced tricks"]


def test_propose_constraints_on_fixtures(app) -> None:
    res = playlist.propose_playlist(
        app,
        ProposePlaylistInput(topic="pandas python", total_duration_min=60, max_video_duration_min=20, language="en"),
    )
    assert res.status == "proposed"
    assert res.total_duration_seconds <= 3600
    assert all(i.duration_seconds <= 1200 for i in res.items)
    assert res.fill_ratio >= 0.9
    assert res.unmet_constraints == []
    assert res.privacy == "private"
    # Language exclusions are counted; unknown language is excluded and counted separately.
    assert res.excluded["language_mismatch"] >= 3
    assert res.excluded["unknown_language"] == 1
    assert res.unknown_metadata["language"] == 1
    assert res.excluded["unknown_duration"] == 1  # the live stream
    assert res.excluded["deleted_or_private"] == 1
    assert res.excluded["private_or_unavailable"] == 2
    assert res.estimated_write_quota == {"units": 50 + 50 * len(res.items)}
    assert {c.name for c in res.constraints_checked} >= {
        "total_duration_not_exceeded",
        "max_video_duration",
        "language",
        "fill_target",
    }


def test_propose_shortfall_reported(app) -> None:
    res = playlist.propose_playlist(
        app,
        ProposePlaylistInput(topic="sourdough bread", total_duration_min=600, max_video_duration_min=30, language="en"),
    )
    assert res.status == "proposed"
    assert res.fill_ratio < 0.9
    assert res.shortfall_seconds == res.target_duration_seconds - res.total_duration_seconds
    assert res.unmet_constraints and "shortfall" in res.unmet_constraints[0]


def test_propose_min_duration(app) -> None:
    res = playlist.propose_playlist(
        app,
        ProposePlaylistInput(
            topic="pandas python",
            total_duration_min=60,
            max_video_duration_min=20,
            min_video_duration_min=14,
            language="en",
        ),
    )
    assert all(i.duration_seconds >= 14 * 60 for i in res.items)
    assert res.excluded["shorter_than_min"] >= 1


def test_no_candidates(app) -> None:
    res = playlist.propose_playlist(
        app,
        ProposePlaylistInput(topic="quantum knitting", total_duration_min=30, max_video_duration_min=10, language="en"),
    )
    assert res.status == "no_candidates"
    assert res.proposal_id is None
