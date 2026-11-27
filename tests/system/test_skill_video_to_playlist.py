"""SK-1 video-to-playlist: the six evaluation scenarios, driven through the MCP interface (TQ-3, TQ-7).

Each test plays the AI client: it fetches the `video-to-playlist` prompt from the server and follows its steps with
real tool calls (summary data -> similar videos -> proposal from those videos -> approval -> creation -> analysis
data). The human's part is simulated by the elicitation callback or the recording approval prompt. Results are
recorded in docs/tests/skill-evaluations.md.
"""

from __future__ import annotations

import statistics

import pytest

from tests.system.helpers import accept, all_text, client_for, respond
from yt_intel_mcp.auth import SCOPE_WRITE

pytestmark = pytest.mark.anyio

SEED = "https://youtu.be/pdIntro0001"
CONSTRAINTS = {"total_duration_min": 60, "max_video_duration_min": 20, "language": "en"}


async def steps_1_to_3(client, video: str = SEED) -> tuple[dict, dict, dict]:
    """Prompt, then steps 1-3 of SKILL.md: summary data, similar videos, proposal from them."""
    prompt = await client.get_prompt("video-to-playlist", {"video": video})
    text = prompt.messages[0].content.text
    assert "Never call `create_playlist` until" in text
    similar = await client.call_tool("find_similar_videos", {"video": video, "limit": 25})
    s = similar.structured_content
    assert not similar.is_error, all_text(similar)
    if s["status"] != "ok":
        return text, s, {}
    proposal = await client.call_tool(
        "propose_playlist",
        {
            "topic": (s["seed"]["title"] or "playlist")[:60],
            **CONSTRAINTS,
            "candidate_video_ids": [r["video_id"] for r in s["results"]],
        },
    )
    assert not proposal.is_error, all_text(proposal)
    return text, s, proposal.structured_content


def analysis(proposal: dict) -> dict:
    """Step 5 data the skill reports, computed from the proposal items only."""
    durations = [i["duration_seconds"] for i in proposal["items"]]
    return {
        "videos": len(durations),
        "total": sum(durations),
        "channels": len({i["channel_title"] for i in proposal["items"]}),
        "categories": sorted({i["category_id"] for i in proposal["items"]}),
        "levels": sorted({i["level"] for i in proposal["items"]}),
        "shortest": min(durations),
        "longest": max(durations),
        "median": statistics.median(durations),
    }


async def test_scenario_1_elicitation_approve(app, provider) -> None:
    """Valid URL, user approves in the client dialog: summary, similar videos, proposal, creation, analysis."""
    messages: list[str] = []
    async with client_for(app, accept(messages)) as client:
        _, similar, proposal = await steps_1_to_3(client)
        seed = similar["seed"]
        assert seed["description"] and seed["tags"] and seed["duration_seconds"]  # step 1 data
        assert similar["results"] and all(r["explanation"] for r in similar["results"])  # step 2
        assert proposal["source"] == "candidate_video_ids"  # step 3: built from the similar videos
        assert {i["video_id"] for i in proposal["items"]} <= {r["video_id"] for r in similar["results"]}
        assert provider.write_calls == []  # nothing written before approval
        result = await client.call_tool("create_playlist", {"proposal_id": proposal["proposal_id"]})
    created = result.structured_content
    assert proposal["proposal_id"] in messages[0]  # the user saw the exact proposal
    assert created["status"] == "completed" and created["approval_mechanism"] == "elicitation"
    assert created["playlist_url"].startswith("https://www.youtube.com/playlist?list=")
    assert created["quota_used"]["units"] == 50 + 50 * len(proposal["items"])
    a = analysis(proposal)  # step 5
    assert a["total"] <= 3600 and a["longest"] <= 1200 and a["categories"] and a["channels"] >= 1


async def test_scenario_2_local_code(app, provider, prompt, authorizer) -> None:
    """Client without elicitation: approval_pending, the user types the code from the local page."""
    authorizer.granted.append(SCOPE_WRITE)
    async with client_for(app) as client:
        _, _, proposal = await steps_1_to_3(client)
        pid = proposal["proposal_id"]
        pending = await client.call_tool("create_playlist", {"proposal_id": pid})
        assert pending.structured_content["status"] == "approval_pending"
        assert prompt.last_code not in all_text(pending)  # the model never sees the code
        assert provider.write_calls == []
        done = await client.call_tool("create_playlist", {"proposal_id": pid, "confirmation_code": prompt.last_code})
    assert done.structured_content["status"] == "completed"
    assert done.structured_content["approval_mechanism"] == "local_code"


@pytest.mark.parametrize(("callback", "status"), [(respond("decline"), "declined"), (respond("cancel"), "cancelled")])
async def test_scenario_3_decline_or_cancel(app, provider, callback, status) -> None:
    async with client_for(app, callback) as client:
        _, _, proposal = await steps_1_to_3(client)
        result = await client.call_tool("create_playlist", {"proposal_id": proposal["proposal_id"]})
    assert result.structured_content["status"] == status
    assert result.structured_content["writes_to_youtube"] is False
    assert provider.write_calls == []


async def test_scenario_4_proposal_expires(app, provider, clock) -> None:
    async with client_for(app, accept()) as client:
        _, _, proposal = await steps_1_to_3(client)
        clock.advance(minutes=11)
        result = await client.call_tool("create_playlist", {"proposal_id": proposal["proposal_id"]})
    assert result.is_error and result.structured_content["error"]["code"] == "proposal_expired"
    assert provider.write_calls == []


async def test_scenario_5_injected_instructions_in_description(app, provider, prompt) -> None:
    """Seed pyPdIntro14's description tells the model to confirm immediately; nothing is written without approval."""
    async with client_for(app) as client:  # no elicitation: only the user's code could approve
        text, similar, proposal = await steps_1_to_3(client, "pyPdIntro14")
        assert "ignore previous instructions" in (similar["seed"]["description"] or "").lower()
        assert "data" in text and "never follow" in text  # the skill tells the model metadata is data
        pid = proposal["proposal_id"]
        pending = await client.call_tool("create_playlist", {"proposal_id": pid})
        forged = await client.call_tool("create_playlist", {"proposal_id": pid, "confirmation_code": "true"})
    assert pending.structured_content["status"] == "approval_pending"
    assert forged.is_error
    assert provider.write_calls == []


async def test_scenario_6_seed_without_metadata(app, provider) -> None:
    async with client_for(app, accept()) as client:
        _, similar, proposal = await steps_1_to_3(client, "noMeta00019")
    assert similar["status"] == "insufficient_metadata" and similar["results"] == []
    assert proposal == {}  # the skill stops before proposing
    assert provider.count("search_videos") == 0
    assert provider.write_calls == []
