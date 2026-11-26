"""TQ-3: FR-1..FR-5 end to end through an in-process MCP client session."""

import json

import pytest

from tests.system.helpers import accept, all_text, client_for
from yt_intel_mcp.auth import SCOPE_WRITE

pytestmark = pytest.mark.anyio

TOOLS = {
    "find_similar_videos",
    "find_similar_channels",
    "recommend_videos",
    "analyze_engagement",
    "propose_playlist",
    "create_playlist",
    "start_authorization",
    "revoke_authorization",
    "clear_cache",
}
PROPOSAL_ARGS = {"topic": "pandas python", "total_duration_min": 60, "max_video_duration_min": 20, "language": "en"}


async def test_tools_registered_with_write_statement(app) -> None:
    async with client_for(app) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert set(tools) == TOOLS
    for name, tool in tools.items():
        assert "Writes to YouTube:" in tool.description, name
        assert tool.input_schema["type"] == "object"
        assert tool.output_schema is not None, name
    assert "Writes to YouTube: YES" in tools["create_playlist"].description
    assert sum("Writes to YouTube: YES" in t.description for t in tools.values()) == 1
    assert tools["find_similar_videos"].annotations.read_only_hint is True


async def test_skills_not_registered(app) -> None:
    async with client_for(app) as client:
        tools = [t.name for t in (await client.list_tools()).tools]
        resources = [str(r.uri) for r in (await client.list_resources()).resources]
    assert not any("skill" in n or "playlist-" in n for n in tools + resources)


async def test_fr1_to_fr4_results_have_summary_and_structure(app) -> None:
    calls = [
        ("find_similar_videos", {"video": "https://youtu.be/pdIntro0001", "limit": 5}),
        ("find_similar_channels", {"channel": "@datadojo", "limit": 3}),
        ("recommend_videos", {"limit": 5, "filters": {"language": "en"}}),
        ("analyze_engagement", {"period": "2025", "compare_to": "2026"}),
    ]
    async with client_for(app) as client:
        for name, args in calls:
            result = await client.call_tool(name, args)
            assert not result.is_error, all_text(result)
            data = result.structured_content
            assert data["summary"] and result.content[0].text == data["summary"]  # UI-1
            assert json.loads(result.content[1].text) == data
            assert data["writes_to_youtube"] is False


async def test_fr5_with_elicitation_accept(app, provider, authorizer) -> None:
    messages: list[str] = []
    async with client_for(app, accept(messages)) as client:
        proposal = await client.call_tool("propose_playlist", PROPOSAL_ARGS)
        p = proposal.structured_content
        # UI-2 contents
        for key in (
            "proposal_id",
            "title",
            "privacy",
            "items",
            "total_duration_seconds",
            "constraints_checked",
            "excluded",
            "unknown_metadata",
            "unmet_constraints",
            "estimated_write_quota",
        ):
            assert key in p
        for item in p["items"]:
            assert {"title", "channel_title", "duration_seconds", "url"} <= set(item)
        assert provider.write_calls == []
        created = await client.call_tool("create_playlist", {"proposal_id": p["proposal_id"]})
    c = created.structured_content
    assert not created.is_error, all_text(created)
    assert c["status"] == "completed" and c["approval_mechanism"] == "elicitation"
    assert c["playlist_url"].startswith("https://www.youtube.com/playlist?list=")
    assert c["privacy"] == "private"
    assert c["quota_used"]["units"] == 50 + 50 * len(p["items"])
    assert c["items_inserted"] == len(p["items"])
    # The elicitation showed the exact proposal.
    assert p["proposal_id"] in messages[0]
    assert all(item["title"] in messages[0] for item in p["items"])
    # Write scope requested only now (incremental authorisation).
    assert authorizer.requested_scopes == [[authorizer.granted[0], SCOPE_WRITE]]


async def test_fr5_with_local_code(app, provider, prompt, authorizer) -> None:
    authorizer.granted.append(SCOPE_WRITE)
    async with client_for(app) as client:  # no elicitation support
        p = (await client.call_tool("propose_playlist", PROPOSAL_ARGS)).structured_content
        pending = await client.call_tool("create_playlist", {"proposal_id": p["proposal_id"]})
        assert pending.structured_content["status"] == "approval_pending"
        assert provider.write_calls == []
        code = prompt.last_code
        assert prompt.shown[-1]["proposal_id"] == p["proposal_id"]
        done = await client.call_tool("create_playlist", {"proposal_id": p["proposal_id"], "confirmation_code": code})
        again = await client.call_tool("create_playlist", {"proposal_id": p["proposal_id"], "confirmation_code": code})
    assert done.structured_content["status"] == "completed"
    assert again.structured_content["status"] == "already_completed"
    assert provider.count("create_playlist") == 1


async def test_resources(app) -> None:
    async with client_for(app, accept()) as client:
        uris = {str(r.uri) for r in (await client.list_resources()).resources}
        assert {"quota://status", "config://server"} <= uris
        p = (await client.call_tool("propose_playlist", PROPOSAL_ARGS)).structured_content
        quota_status = json.loads((await client.read_resource("quota://status")).contents[0].text)
        config = json.loads((await client.read_resource("config://server")).contents[0].text)
        prop = json.loads((await client.read_resource(f"proposal://{p['proposal_id']}")).contents[0].text)
    assert set(quota_status["buckets"]) == {"search_calls", "units"}
    assert quota_status["buckets"]["search_calls"]["consumed"] >= 1
    assert config["transport"] == "stdio" and config["approval"]["default_privacy"] == "private"
    assert prop["state"] == "PROPOSED"
    blob = json.dumps([quota_status, config, prop]).lower()
    for forbidden in ("token", "secret", "code_hash", "code_salt", "password", "refresh"):
        assert forbidden not in blob


async def test_clear_cache_and_revoke(app, authorizer) -> None:
    async with client_for(app) as client:
        await client.call_tool("find_similar_videos", {"video": "pdIntro0001"})
        assert app.cache.count() > 0
        cleared = await client.call_tool("clear_cache", {})
        assert cleared.structured_content["entries_deleted"] > 0 and app.cache.count() == 0
        await client.call_tool("find_similar_videos", {"video": "pdIntro0001"})
        revoked = await client.call_tool("revoke_authorization", {})
        after = await client.call_tool("find_similar_videos", {"video": "pdIntro0001"})
    assert revoked.structured_content["status"] == "revoked"
    assert authorizer.revoked and app.cache.count() == 0
    assert after.is_error and after.structured_content["error"]["code"] == "authorization_required"


async def test_start_authorization_requests_read_scope_only(app, authorizer) -> None:
    async with client_for(app) as client:
        result = await client.call_tool("start_authorization", {})
    assert result.structured_content["status"] == "authorized"
    assert authorizer.requested_scopes == [["https://www.googleapis.com/auth/youtube.readonly"]]
