from datetime import date

import pytest

from yt_intel_mcp.schemas import AnalyzeEngagementInput, VideoMeta
from yt_intel_mcp.services import engagement
from yt_intel_mcp.services.engagement import compare, duration_stats, parse_period, trends

TODAY = date(2026, 3, 10)


@pytest.mark.parametrize(
    ("value", "start", "end"),
    [
        ("2025", date(2025, 1, 1), date(2025, 12, 31)),
        ("2025-Q1", date(2025, 1, 1), date(2025, 3, 31)),
        ("2025-Q4", date(2025, 10, 1), date(2025, 12, 31)),
        ("2024-02", date(2024, 2, 1), date(2024, 2, 29)),
        ("2025-12", date(2025, 12, 1), date(2025, 12, 31)),
        ("last_30_days", date(2026, 2, 9), TODAY),
        ("2025-01-05..2025-02-04", date(2025, 1, 5), date(2025, 2, 4)),
    ],
)
def test_parse_period(value, start, end) -> None:
    p = parse_period(value, TODAY)
    assert (p.start, p.end) == (start, end)


def test_parse_period_all_and_invalid() -> None:
    assert parse_period("all", TODAY).start is None
    with pytest.raises(ValueError):
        parse_period("2025-02-04..2025-01-05", TODAY)


def test_duration_buckets_mean_median() -> None:
    vids = [VideoMeta(video_id=str(i) * 11, duration_seconds=s) for i, s in enumerate([60, 600, 1800, 4000, None])]
    stats = duration_stats("likes", vids)
    assert stats.buckets == {"<4 min": 1, "4-20 min": 1, "20-60 min": 1, ">60 min": 1}
    assert stats.unknown_duration == 1
    assert stats.mean_minutes == round((60 + 600 + 1800 + 4000) / 4 / 60, 2)
    assert stats.median_minutes == round((600 + 1800) / 2 / 60, 2)


def test_trends_label_timestamp_source_and_count_missing() -> None:
    out = trends("playlist_items", [date(2025, 1, 3), date(2025, 1, 20), date(2025, 4, 1), None])
    month, quarter = out
    assert month.timestamp_source == "playlist-item added date"
    assert [(p.period, p.count) for p in month.points] == [("2025-01", 2), ("2025-04", 1)]
    assert [(p.period, p.count) for p in quarter.points] == [("2025-Q1", 2), ("2025-Q2", 1)]
    assert month.excluded_without_timestamp == 1


def test_compare_labels() -> None:
    days = [date(2025, 1, 5), date(2025, 2, 5), date(2026, 1, 5)]
    same_len = compare("likes", days, parse_period("2025", TODAY), parse_period("2026", TODAY))
    assert same_len.comparable and same_len.change_pct == 100.0
    assert "video publish date" in same_len.label
    diff_len = compare("likes", days, parse_period("2025", TODAY), parse_period("2026-01", TODAY))
    assert not diff_len.comparable and diff_len.label.startswith("not comparable")
    empty = compare("subscriptions", days, parse_period("2024", TODAY), parse_period("2023", TODAY))
    assert not empty.comparable and empty.change_pct is None


def test_service_aggregates(app) -> None:
    res = engagement.analyze_engagement(app, AnalyzeEngagementInput(period="all"))
    assert res.status == "ok"
    assert res.totals == {"likes": 8, "subscriptions": 4, "playlist_items": 5}
    likes = res.top_channels["likes"]
    assert likes[0].label == "Data Dojo" and likes[0].count == 4 and likes[0].share == 0.5
    assert abs(sum(c.share for c in likes) - 1.0) < 1e-6
    assert res.top_categories["likes"][0].label == "Education"
    assert [s.subscribed_at[:10] for s in res.subscriptions] == ["2026-01-20", "2025-11-05", "2025-07-02", "2025-03-14"]
    pl_month = next(t for t in res.trends if t.source == "playlist_items" and t.granularity == "month")
    assert pl_month.excluded_without_timestamp == 1
    assert {t.timestamp_source for t in res.trends} == {
        "video publish date",
        "subscription date",
        "playlist-item added date",
    }
    text = res.model_dump_json().lower()
    assert "watched" not in text and "watch history" not in text and "liked at" not in text
