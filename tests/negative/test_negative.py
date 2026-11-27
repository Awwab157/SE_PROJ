"""TQ-4: negative paths. Every error has a code, a cause and a next step, and leaks nothing."""

import json

import httplib2
import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

from tests.conftest import make_app
from tests.system.helpers import accept, all_text, client_for
from yt_intel_mcp import quota
from yt_intel_mcp.auth import SCOPE_READ, SCOPE_WRITE, StaticAuthorizer
from yt_intel_mcp.clock import FakeClock
from yt_intel_mcp.config import load_quota_config
from yt_intel_mcp.errors import (
    Forbidden,
    InvalidGrant,
    NotFound,
    QuotaExceeded,
    RateLimited,
    Transient,
    YoutubeSignupRequired,
)
from yt_intel_mcp.providers.fixture import FixtureProvider
from yt_intel_mcp.providers.live import MAX_DELAY_SECONDS, LiveProvider, map_http_error
from yt_intel_mcp.quota import QuotaConfig, QuotaManager
from yt_intel_mcp.storage import Database

FAKE_TOKEN = "ya29.FAKE-token-for-tests-0123456789"


def assert_clean_error(result, code: str | None = None) -> dict:
    assert result.is_error
    err = result.structured_content["error"]
    assert err["cause"] and err["next_step"]
    if code:
        assert err["code"] == code, err
    text = all_text(result)
    assert "Traceback" not in text and 'File "' not in text
    assert "ya29." not in text and "refresh_token" not in text
    return err


# --- via MCP ----------------------------------------------------------------------------------------

pytestmark_anyio = pytest.mark.anyio


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("tool", "args", "code"),
    [
        ("find_similar_videos", {"video": "not a video"}, "invalid_input"),
        ("find_similar_videos", {"video": "https://vimeo.com/1"}, "invalid_input"),
        ("find_similar_videos", {"video": "pdIntro0001", "limit": 500}, "invalid_input"),
        ("find_similar_videos", {"video": "pyPriv00016"}, "not_found"),
        ("find_similar_videos", {"video": "deletedVid1"}, "not_found"),
        ("find_similar_channels", {"channel": "just words"}, "invalid_input"),
        ("find_similar_channels", {"channel": "@nobodyhere"}, "not_found"),
        ("recommend_videos", {"filters": {"language": "klingon"}}, "invalid_input"),
        ("recommend_videos", {"filters": {"bogus": 1}}, "invalid_input"),
        ("analyze_engagement", {"period": "yesterday"}, "invalid_input"),
        (
            "propose_playlist",
            {"topic": "x", "total_duration_min": 10, "max_video_duration_min": 5, "language": "en"},
            "invalid_input",
        ),
        (
            "propose_playlist",
            {"topic": "pandas", "total_duration_min": 10, "max_video_duration_min": 50, "language": "en"},
            "invalid_input",
        ),
        ("create_playlist", {"proposal_id": "nope"}, "invalid_input"),
        ("create_playlist", {"proposal_id": "a" * 32}, "proposal_not_found"),
    ],
)
async def test_errors_are_structured(app, provider, tool, args, code) -> None:
    async with client_for(app) as client:
        result = await client.call_tool(tool, args)
    assert_clean_error(result, code)
    assert provider.write_calls == []


@pytest.mark.anyio
async def test_invalid_grant_requires_reauthorisation(tmp_path, fixture_data, prompt, clock) -> None:
    auth = StaticAuthorizer([SCOPE_READ], error=InvalidGrant("The stored authorisation was revoked."))
    app = make_app(tmp_path, FixtureProvider(fixture_data, authorizer=auth), auth, prompt, clock)
    async with client_for(app) as client:
        result = await client.call_tool("find_similar_videos", {"video": "pdIntro0001"})
    err = assert_clean_error(result, "reauthorization_required")
    assert "start_authorization" in err["next_step"] and "7 days" in err["next_step"]


@pytest.mark.anyio
async def test_not_authorised(tmp_path, fixture_data, prompt, clock) -> None:
    auth = StaticAuthorizer([])
    app = make_app(tmp_path, FixtureProvider(fixture_data, authorizer=auth), auth, prompt, clock)
    async with client_for(app) as client:
        result = await client.call_tool("recommend_videos", {})
    assert "start_authorization" in assert_clean_error(result, "authorization_required")["next_step"]


@pytest.mark.anyio
async def test_youtube_signup_required(app, provider, authorizer) -> None:
    authorizer.granted.append(SCOPE_WRITE)
    provider.inject_error("create_playlist", YoutubeSignupRequired("No channel."))
    async with client_for(app, accept()) as client:
        p = await client.call_tool(
            "propose_playlist",
            {"topic": "pandas python", "total_duration_min": 30, "max_video_duration_min": 20, "language": "en"},
        )
        result = await client.call_tool("create_playlist", {"proposal_id": p.structured_content["proposal_id"]})
    err = assert_clean_error(result, "youtube_signup_required")
    assert "YouTube channel" in err["next_step"]
    assert provider.inserted_items == [] and provider.created_playlists == []


@pytest.mark.anyio
async def test_unexpected_error_does_not_leak(app, provider) -> None:
    provider.inject_error("get_videos", RuntimeError(f"secret {FAKE_TOKEN} at /home/user/file.py line 3"))
    async with client_for(app) as client:
        result = await client.call_tool("find_similar_videos", {"video": "pdIntro0001"})
    err = assert_clean_error(result, "internal_error")
    assert FAKE_TOKEN not in json.dumps(err) and "file.py" not in all_text(result)


@pytest.mark.anyio
async def test_quota_budget_error_via_mcp(app) -> None:
    from tests.conftest import consume

    consume(app, search_calls=100)
    async with client_for(app) as client:
        result = await client.call_tool("find_similar_videos", {"video": "pdIntro0001"})
    err = assert_clean_error(result, "quota_budget_exceeded")
    assert err["details"]["remaining"]["search_calls"] == 0


# --- empty account / 1,000-like limit -----------------------------------------------------------------


def _with_account(tmp_path, fixture_data, prompt, clock, account, extra_videos=()):
    data = dict(fixture_data)
    data["account"] = account
    data["videos"] = list(fixture_data["videos"]) + list(extra_videos)
    auth = StaticAuthorizer([SCOPE_READ])
    return make_app(tmp_path, FixtureProvider(data, authorizer=auth), auth, prompt, clock)


def test_empty_account(tmp_path, fixture_data, prompt, clock) -> None:
    from yt_intel_mcp.schemas import AnalyzeEngagementInput, RecommendVideosInput
    from yt_intel_mcp.services import engagement, recommendations

    app = _with_account(tmp_path, fixture_data, prompt, clock, {})
    rec = recommendations.recommend_videos(app, RecommendVideosInput())
    assert rec.status == "empty_account" and rec.results == [] and "no likes" in rec.summary
    eng = engagement.analyze_engagement(app, AnalyzeEngagementInput())
    assert eng.status == "empty_account"


def test_1000_like_limit_is_stated(tmp_path, fixture_data, prompt, clock) -> None:
    from yt_intel_mcp.schemas import AnalyzeEngagementInput, RecommendVideosInput
    from yt_intel_mcp.services import engagement, recommendations

    template = fixture_data["videos"][0]
    extra = []
    for i in range(1000):
        v = json.loads(json.dumps(template))
        v["id"] = f"L{i:010d}"
        extra.append(v)
    app = _with_account(tmp_path, fixture_data, prompt, clock, {"liked_video_ids": [v["id"] for v in extra]}, extra)
    rec = recommendations.recommend_videos(app, RecommendVideosInput())
    assert any("1,000" in n for n in rec.data_limits)
    eng = engagement.analyze_engagement(app, AnalyzeEngagementInput())
    assert any("1,000" in n for n in eng.data_limits)


@pytest.mark.anyio
async def test_skill_prompt_rejects_invalid_video(app) -> None:
    from mcp import MCPError

    async with client_for(app) as client:
        with pytest.raises(MCPError) as info:
            await client.get_prompt("video-to-playlist", {"video": "not a video"})
    message = str(info.value)
    assert "invalid_input" in message and "Next step" in message
    assert "Traceback" not in message and 'File "' not in message


# --- live provider error handling (fake Google service, no network) ------------------------------------


def http_error(status: int, reason: str | None) -> HttpError:
    body = {"error": {"code": status, "message": "x", "errors": [{"reason": reason}] if reason else []}}
    return HttpError(httplib2.Response({"status": status}), json.dumps(body).encode())


class FakeRequest:
    def __init__(self, outcomes: list):
        self.outcomes = outcomes

    def execute(self, num_retries=0):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeService:
    """Mimics googleapiclient's resource objects; every request pops the next outcome."""

    def __init__(self, outcomes: list):
        self.outcomes = outcomes
        self.requests = 0

    def __getattr__(self, name):
        def resource():
            svc = self

            class R:
                def list(self, **kw):
                    svc.requests += 1
                    return FakeRequest(svc.outcomes)

                def insert(self, **kw):
                    svc.requests += 1
                    return FakeRequest(svc.outcomes)

            return R()

        return resource


@pytest.fixture
def live_env(tmp_path):
    mgr = QuotaManager(Database(tmp_path / "l.db"), QuotaConfig(load_quota_config()), FakeClock())

    def make(outcomes, granted=(SCOPE_READ,)):
        service = FakeService(list(outcomes))
        sleeps: list[float] = []
        provider = LiveProvider(
            StaticAuthorizer(list(granted)), service_factory=lambda creds: service, sleep=sleeps.append, rng=lambda: 1.0
        )
        return provider, service, sleeps

    return mgr, make


def run_reserved(mgr, fn):
    r = mgr.reserve({"videos.list": 1, "playlists.insert": 1}, label="t")
    try:
        with quota.active(r):
            return fn()
    finally:
        r.release_unused()


def test_quota_exceeded_is_not_retried(live_env) -> None:
    mgr, make = live_env
    provider, service, sleeps = make([http_error(403, "quotaExceeded")])
    with pytest.raises(QuotaExceeded):
        run_reserved(mgr, lambda: provider.get_videos(["pdIntro0001"]))
    assert service.requests == 1 and sleeps == []
    assert mgr.status()["buckets"]["units"]["remaining"] == 0  # no further calls today


def test_rate_limit_retried_at_most_three_times(live_env) -> None:
    mgr, make = live_env
    provider, service, sleeps = make([http_error(429, None)] * 5)
    with pytest.raises(RateLimited):
        run_reserved(mgr, lambda: provider.get_videos(["pdIntro0001"]))
    assert service.requests == 4  # 1 attempt + 3 retries
    assert len(sleeps) == 3 and all(0 < s <= MAX_DELAY_SECONDS for s in sleeps)
    assert sleeps == sorted(sleeps)  # exponential


def test_rate_limit_reason_403_retried_then_succeeds(live_env) -> None:
    mgr, make = live_env
    provider, service, _ = make([http_error(403, "rateLimitExceeded"), http_error(503, None), {"items": []}])
    assert run_reserved(mgr, lambda: provider.get_videos(["pdIntro0001"])) == []
    assert service.requests == 3


def test_writes_are_never_retried(live_env) -> None:
    mgr, make = live_env
    provider, service, sleeps = make([http_error(500, None), {"id": "PLx"}], granted=(SCOPE_READ, SCOPE_WRITE))
    with pytest.raises(Transient):
        run_reserved(mgr, lambda: provider.create_playlist("t", "d", "private"))
    assert service.requests == 1 and sleeps == []


def test_refresh_error_maps_to_invalid_grant(live_env) -> None:
    mgr, make = live_env
    provider, _, _ = make([RefreshError("invalid_grant: Token has been expired or revoked.")])
    with pytest.raises(InvalidGrant) as err:
        run_reserved(mgr, lambda: provider.get_videos(["pdIntro0001"]))
    assert "invalid_grant" not in err.value.cause


@pytest.mark.parametrize(
    ("status", "reason", "expected"),
    [
        (403, "youtubeSignupRequired", YoutubeSignupRequired),
        (404, "videoNotFound", NotFound),
        (403, "forbidden", Forbidden),
        (403, "dailyLimitExceeded", QuotaExceeded),
        (500, None, Transient),
        (401, None, InvalidGrant),
    ],
)
def test_error_mapping(status, reason, expected) -> None:
    err = map_http_error(http_error(status, reason))
    assert isinstance(err, expected)
    assert err.cause and err.next_step
