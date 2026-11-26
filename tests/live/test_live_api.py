"""TQ-5: live YouTube Data API tests.

Run only from ``.github/workflows/live-api.yml`` (``pytest -m live``) with secrets from GitHub Actions:
* ``YT_INTEL_LIVE_TOKEN_JSON``: authorized-user JSON (client_id, client_secret, refresh_token, scopes) for
  a dedicated test account with **read-only** scope.
* ``YT_INTEL_LIVE_VIDEO``: a public video ID owned by the team.
* ``YT_INTEL_LIVE_CHANNEL``: a public channel ID or @handle owned by the team.

A fixed quota budget (``LIVE_BUDGET``) caps what one run can spend. No live test writes to YouTube.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from yt_intel_mcp.auth import AuthManager, MemoryTokenStore
from yt_intel_mcp.config import config_dir
from yt_intel_mcp.providers.live import LiveProvider
from yt_intel_mcp.schemas import AnalyzeEngagementInput, FindSimilarChannelsInput, FindSimilarVideosInput
from yt_intel_mcp.server import build_app
from yt_intel_mcp.services import engagement, similar_channels, similar_videos

pytestmark = pytest.mark.live
LIVE_BUDGET = {"search_calls": 6, "units": 800}

TOKEN = os.environ.get("YT_INTEL_LIVE_TOKEN_JSON")
VIDEO = os.environ.get("YT_INTEL_LIVE_VIDEO")
CHANNEL = os.environ.get("YT_INTEL_LIVE_CHANNEL")


@pytest.fixture
def live_app(tmp_path: Path):
    if not TOKEN:
        pytest.skip("YT_INTEL_LIVE_TOKEN_JSON is not set")
    cfg = yaml.safe_load((config_dir() / "quota.yaml").read_text())
    cfg["buckets"] = dict(LIVE_BUDGET)
    conf = tmp_path / "config"
    conf.mkdir()
    (conf / "quota.yaml").write_text(yaml.safe_dump(cfg))
    (conf / "similarity.yaml").write_text((config_dir() / "similarity.yaml").read_text())
    auth = AuthManager(None, MemoryTokenStore(TOKEN))
    return build_app(
        state_dir=tmp_path / "state",
        raw_provider=LiveProvider(auth),
        authorizer=auth,
        provider_mode="live",
        config_dir=conf,
    )


def _within_budget(app) -> None:
    for bucket, data in app.quota.status()["buckets"].items():
        assert data["consumed"] <= LIVE_BUDGET[bucket]


@pytest.mark.skipif(not VIDEO, reason="YT_INTEL_LIVE_VIDEO is not set")
def test_live_find_similar_videos(live_app) -> None:
    res = similar_videos.find_similar_videos(live_app, FindSimilarVideosInput(video=VIDEO, limit=5))
    assert res.status in ("ok", "no_candidates", "insufficient_metadata")
    assert all(r.video_id != VIDEO for r in res.results)
    _within_budget(live_app)


@pytest.mark.skipif(not CHANNEL, reason="YT_INTEL_LIVE_CHANNEL is not set")
def test_live_find_similar_channels(live_app) -> None:
    res = similar_channels.find_similar_channels(live_app, FindSimilarChannelsInput(channel=CHANNEL, limit=3))
    assert res.status in ("ok", "no_candidates", "insufficient_metadata", "ambiguous_channel")
    _within_budget(live_app)


def test_live_engagement_read_only(live_app) -> None:
    res = engagement.analyze_engagement(live_app, AnalyzeEngagementInput(period="all"))
    assert res.status in ("ok", "empty_account")
    _within_budget(live_app)
