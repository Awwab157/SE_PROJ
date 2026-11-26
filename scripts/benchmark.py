"""NFR-2 benchmark: local processing time vs (simulated) API wait time, on fixtures.

The fixture provider answers instantly, so API wait is simulated as ``calls x --latency`` (default 0.25 s
per HTTP request, a typical YouTube Data API round trip). Local processing is the measured wall time minus
the time spent inside the fixture provider. Targets (TBD-3) are set from these measurements.

Usage: ``python scripts/benchmark.py [--runs 5] [--latency 0.25] [--json out.json]``
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from yt_intel_mcp.approval import RecordingApprovalPrompt  # noqa: E402
from yt_intel_mcp.auth import SCOPE_READ, StaticAuthorizer  # noqa: E402
from yt_intel_mcp.clock import FakeClock  # noqa: E402
from yt_intel_mcp.providers.base import API_METHODS  # noqa: E402
from yt_intel_mcp.providers.fixture import FixtureProvider, load_fixture_data  # noqa: E402
from yt_intel_mcp.schemas import (  # noqa: E402
    AnalyzeEngagementInput,
    FindSimilarChannelsInput,
    FindSimilarVideosInput,
    ProposePlaylistInput,
    RecommendVideosInput,
)
from yt_intel_mcp.server import build_app  # noqa: E402
from yt_intel_mcp.services import (  # noqa: E402
    engagement,
    playlist,
    recommendations,
    similar_channels,
    similar_videos,
)


class TimedProvider:
    """Delegates to the fixture provider and measures time spent inside it."""

    def __init__(self, inner: FixtureProvider) -> None:
        self.inner = inner
        self.authorizer = inner.authorizer
        self.provider_seconds = 0.0

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self.inner, name)
        if name not in API_METHODS:
            return attr

        def timed(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return attr(*args, **kwargs)
            finally:
                self.provider_seconds += time.perf_counter() - start

        return timed


WORKFLOWS = {
    "find_similar_videos": lambda app: similar_videos.find_similar_videos(
        app, FindSimilarVideosInput(video="pdIntro0001", limit=10)
    ),
    "find_similar_channels": lambda app: similar_channels.find_similar_channels(
        app, FindSimilarChannelsInput(channel="@datadojo", limit=10)
    ),
    "recommend_videos": lambda app: recommendations.recommend_videos(app, RecommendVideosInput(limit=10)),
    "analyze_engagement": lambda app: engagement.analyze_engagement(
        app, AnalyzeEngagementInput(period="2025", compare_to="2026")
    ),
    "propose_playlist": lambda app: playlist.propose_playlist(
        app,
        ProposePlaylistInput(topic="pandas python", total_duration_min=60, max_video_duration_min=20, language="en"),
    ),
}


def run_once(name: str, latency: float, data: dict) -> dict[str, float]:
    auth = StaticAuthorizer([SCOPE_READ])
    fixture = FixtureProvider(data, authorizer=auth)
    timed = TimedProvider(fixture)
    with tempfile.TemporaryDirectory() as tmp:
        app = build_app(
            state_dir=Path(tmp),
            raw_provider=timed,
            authorizer=auth,
            approval_prompt=RecordingApprovalPrompt(),
            clock=FakeClock(),
            provider_mode="fixture",
        )
        start = time.perf_counter()
        WORKFLOWS[name](app)
        total = time.perf_counter() - start
    calls = len(fixture.calls)
    return {
        "local_processing_s": total - timed.provider_seconds,
        "api_calls": calls,
        "simulated_api_wait_s": calls * latency,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--latency", type=float, default=0.25, help="simulated seconds per API request")
    parser.add_argument("--json", type=Path, help="write raw results as JSON")
    args = parser.parse_args(argv)
    data = load_fixture_data()
    report: dict[str, Any] = {}
    print(f"{'workflow':<24}{'local p50 (ms)':>16}{'local max (ms)':>16}{'API calls':>11}{'API wait (s)':>14}")
    for name in WORKFLOWS:
        runs = [run_once(name, args.latency, data) for _ in range(args.runs)]
        local = [r["local_processing_s"] * 1000 for r in runs]
        report[name] = {
            "local_processing_ms_p50": round(statistics.median(local), 1),
            "local_processing_ms_max": round(max(local), 1),
            "api_calls": runs[0]["api_calls"],
            "simulated_api_wait_s": round(runs[0]["simulated_api_wait_s"], 2),
        }
        r = report[name]
        print(
            f"{name:<24}{r['local_processing_ms_p50']:>16}{r['local_processing_ms_max']:>16}"
            f"{r['api_calls']:>11}{r['simulated_api_wait_s']:>14}"
        )
    if args.json:
        args.json.write_text(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
