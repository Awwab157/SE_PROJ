from yt_intel_mcp.config import load_similarity_config
from yt_intel_mcp.schemas import VideoMeta
from yt_intel_mcp.similarity import ChannelProfile, keyword_terms, rank_channels, score_videos

WEIGHTS = load_similarity_config()["video_weights"]


def v(vid: str, title: str, tags=(), cat="27", ch="C1", dur=600, lang="en", desc="") -> VideoMeta:
    return VideoMeta(
        video_id=vid,
        title=title,
        description=desc,
        tags=list(tags),
        category_id=cat,
        channel_id=ch,
        duration_seconds=dur,
        language=lang,
    )


SEED = v("seed0000000", "Pandas groupby tutorial", ["pandas", "groupby", "python"])
CANDS = [
    v("b0000000000", "Pandas groupby aggregation explained", ["pandas", "groupby"]),
    v("a0000000000", "Sourdough starter guide", ["bread"], cat="26", ch="C9", dur=1200),
    v("c0000000000", "Python pandas merge", ["pandas", "python"], ch="C2"),
]


def test_weights_sum_to_one() -> None:
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_ordering_and_explanations() -> None:
    ranked = score_videos(SEED, CANDS, WEIGHTS)
    assert [s.video.video_id for s in ranked][0] == "b0000000000"
    assert ranked[-1].video.video_id == "a0000000000"
    top = ranked[0]
    assert "shared tags: groupby, pandas" in top.explanation
    assert "same category" in top.explanation
    assert set(top.components) == set(WEIGHTS)


def test_deterministic() -> None:
    first = [(s.video.video_id, s.score) for s in score_videos(SEED, CANDS, WEIGHTS)]
    for _ in range(3):
        assert [(s.video.video_id, s.score) for s in score_videos(SEED, list(reversed(CANDS)), WEIGHTS)] == first


def test_ties_broken_by_id() -> None:
    twins = [v("zz000000000", "Identical title"), v("aa000000000", "Identical title")]
    ranked = score_videos(v("seed0000000", "Identical title"), twins, WEIGHTS)
    assert ranked[0].score == ranked[1].score
    assert [s.video.video_id for s in ranked] == ["aa000000000", "zz000000000"]


def test_unknown_duration_scores_zero_not_crash() -> None:
    ranked = score_videos(SEED, [v("x0000000000", "Pandas groupby", dur=None)], WEIGHTS)
    assert ranked[0].components["duration_closeness"] == 0.0


def test_keyword_terms_prefers_title_and_is_stable() -> None:
    terms = keyword_terms("Pandas GroupBy tutorial", ["python"], "Learn pandas today http://x.y", 3)
    assert terms[0] == "pandas"
    assert "http" not in terms
    assert terms == keyword_terms("Pandas GroupBy tutorial", ["python"], "Learn pandas today http://x.y", 3)


def test_subscriber_count_cannot_outrank_content_similarity() -> None:
    seed = ChannelProfile("S", "Seed", "pandas python data analysis dataframes", 100000, 4.0, "en")
    relevant_small = ChannelProfile("Z1", "Small", "pandas python data analysis", 10, 0.1, "de")
    popular_off_topic = ChannelProfile("A1", "Popular", "pandas cooking recipes kitchen food", 100000, 4.0, "en")
    weights = {"subscriber_closeness": 0.4, "upload_cadence": 0.3, "language_match": 0.3}
    ranked = rank_channels(seed, [popular_off_topic, relevant_small], weights)
    assert ranked[0].profile.channel_id == "Z1"
    assert ranked[0].score > ranked[1].score
    assert ranked[1].secondary_score > ranked[0].secondary_score


def test_secondary_breaks_exact_content_ties_only() -> None:
    seed = ChannelProfile("S", "Seed", "astronomy telescopes", 5000, 2.0, "en")
    a = ChannelProfile("B2", "Twin B", "astronomy telescopes", 5000, 2.0, "en")
    b = ChannelProfile("A2", "Twin A", "astronomy telescopes", 10, 0.1, "fr")
    ranked = rank_channels(seed, [b, a], {"subscriber_closeness": 1.0})
    assert ranked[0].score == ranked[1].score
    assert ranked[0].profile.channel_id == "B2"
