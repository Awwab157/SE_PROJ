import pytest
from pydantic import ValidationError

from yt_intel_mcp.schemas import (
    AnalyzeEngagementInput,
    CreatePlaylistInput,
    FindSimilarChannelsInput,
    FindSimilarVideosInput,
    ProposePlaylistInput,
    RecommendFilters,
    RecommendVideosInput,
    primary_language,
)

OK_PROPOSAL = dict(topic="pandas", total_duration_min=60, max_video_duration_min=20, language="en")


@pytest.mark.parametrize("limit", [0, -1, 51])
def test_limits(limit) -> None:
    with pytest.raises(ValidationError):
        FindSimilarVideosInput(video="x", limit=limit)
    with pytest.raises(ValidationError):
        FindSimilarChannelsInput(channel="x", limit=limit)
    with pytest.raises(ValidationError):
        RecommendVideosInput(limit=limit)


@pytest.mark.parametrize(
    "override",
    [
        {"total_duration_min": 0},
        {"total_duration_min": -5},
        {"max_video_duration_min": 0},
        {"max_video_duration_min": 61},
        {"min_video_duration_min": 25},
        {"language": "english"},
        {"language": "xx"},
        {"topic": "ab"},
        {"topic": "x" * 101},
        {"privacy": "secret"},
    ],
)
def test_propose_validation(override) -> None:
    with pytest.raises(ValidationError):
        ProposePlaylistInput(**{**OK_PROPOSAL, **override})


def test_propose_valid_defaults_private() -> None:
    assert ProposePlaylistInput(**OK_PROPOSAL).privacy == "private"
    assert ProposePlaylistInput(**{**OK_PROPOSAL, "language": "DE"}).language == "de"


def test_recommend_filters() -> None:
    with pytest.raises(ValidationError):
        RecommendFilters(language="klingon")
    with pytest.raises(ValidationError):
        RecommendFilters(category="music")
    with pytest.raises(ValidationError):
        RecommendFilters(unknown=1)
    assert RecommendFilters(max_duration_min=10, language="en", category="27").category == "27"


@pytest.mark.parametrize("period", ["yesterday", "2025-Q5", "2025-13", "last_days", "2025/01"])
def test_engagement_period_validation(period) -> None:
    with pytest.raises(ValidationError):
        AnalyzeEngagementInput(period=period)


def test_create_input_validation() -> None:
    with pytest.raises(ValidationError):
        CreatePlaylistInput(proposal_id="not-a-uuid")
    with pytest.raises(ValidationError):
        CreatePlaylistInput(proposal_id="a" * 32, confirmation=True)


def test_primary_language() -> None:
    assert primary_language("en-US") == "en"
    assert primary_language("zxx") is None
    assert primary_language(None) is None
