"""TQ-6 (quota) and TQ-9 (proposal / quota concurrency)."""

import threading

import pytest

from tests.conftest import consume
from yt_intel_mcp.auth import SCOPE_READ, SCOPE_WRITE
from yt_intel_mcp.errors import (
    ConfirmationInvalid,
    ProposalExpired,
    ProposalNotFound,
    QuotaBudgetExceeded,
    Transient,
)
from yt_intel_mcp.schemas import FindSimilarVideosInput, ProposePlaylistInput
from yt_intel_mcp.services import playlist as ps
from yt_intel_mcp.services import similar_videos

PROPOSAL = ProposePlaylistInput(topic="pandas python", total_duration_min=60, max_video_duration_min=20, language="en")


def propose(app):
    res = ps.propose_playlist(app, PROPOSAL)
    assert res.status == "proposed"
    return res


def approve_with_code(app, prompt, pid):
    p = ps.load_for_create(app, pid)
    ps.issue_code(app, p)
    return ps.confirm_code(app, ps.load_for_create(app, pid), prompt.last_code)


# --- TQ-6 -----------------------------------------------------------------------------------------------


def test_over_budget_rejected_with_zero_provider_calls(app, provider) -> None:
    consume(app, search_calls=100)
    with pytest.raises(QuotaBudgetExceeded) as err:
        similar_videos.find_similar_videos(app, FindSimilarVideosInput(video="pdIntro0001"))
    assert provider.calls == []
    d = err.value.details
    assert d["remaining"]["search_calls"] == 0 and d["limit"]["search_calls"] == 100
    assert d["estimated"]["search_calls"] >= 1
    assert "estimated" in err.value.cause and "remaining" in err.value.cause


def test_playlist_write_quota_reserved_before_any_write(app, provider, prompt, authorizer) -> None:
    authorizer.granted.append(SCOPE_WRITE)
    res = propose(app)
    p = approve_with_code(app, prompt, res.proposal_id)
    consume(app, units=10000 - 100)  # not enough for 50 + 50 * n
    with pytest.raises(QuotaBudgetExceeded):
        ps.execute_creation(app, p)
    assert provider.write_calls == []
    assert ps.load_for_create(app, p.id).state == ps.State.APPROVED


# --- TQ-9 -----------------------------------------------------------------------------------------------


def test_proposal_expiry_via_clock(app, provider, prompt, clock) -> None:
    res = propose(app)
    clock.advance(minutes=10, seconds=1)
    with pytest.raises(ProposalExpired):
        ps.load_for_create(app, res.proposal_id)
    assert provider.write_calls == []


def test_unknown_proposal(app) -> None:
    with pytest.raises(ProposalNotFound):
        ps.load_for_create(app, "f" * 32)


def test_code_is_single_use(app, provider, prompt, authorizer) -> None:
    authorizer.granted.append(SCOPE_WRITE)
    res = propose(app)
    p = approve_with_code(app, prompt, res.proposal_id)
    ps.execute_creation(app, p, "local_code")
    with pytest.raises(ConfirmationInvalid):
        ps.confirm_code(app, ps.load_for_create(app, res.proposal_id), prompt.last_code)
    assert len(provider.created_playlists) == 1


def test_wrong_code_attempts_invalidate_code(app, provider, prompt) -> None:
    res = propose(app)
    ps.issue_code(app, ps.load_for_create(app, res.proposal_id))
    for _ in range(3):
        with pytest.raises(ConfirmationInvalid):
            ps.confirm_code(app, ps.load_for_create(app, res.proposal_id), "WRONG234")
    # The real code no longer works after too many failures.
    with pytest.raises(ConfirmationInvalid):
        ps.confirm_code(app, ps.load_for_create(app, res.proposal_id), prompt.last_code)
    assert provider.write_calls == []


def test_repeated_confirmation_creates_at_most_one_playlist(app, provider, prompt, authorizer) -> None:
    authorizer.granted.append(SCOPE_WRITE)
    res = propose(app)
    p = approve_with_code(app, prompt, res.proposal_id)
    first = ps.execute_creation(app, p, "local_code")
    assert first.status == "completed"
    again = ps.load_for_create(app, res.proposal_id)
    assert again.state == ps.State.COMPLETED
    repeat = ps.existing_result(again)
    assert repeat.status == "already_completed" and repeat.playlist_id == first.playlist_id
    assert provider.count("create_playlist") == 1
    assert len(provider.inserted_items) == len(res.items)


def test_failure_after_playlist_insert_resumes_without_duplicate(app, provider, prompt, authorizer) -> None:
    authorizer.granted.append(SCOPE_WRITE)
    res = propose(app)
    p = approve_with_code(app, prompt, res.proposal_id)
    provider.inject_error("add_playlist_item", Transient("boom"))
    first = ps.execute_creation(app, p, "local_code")
    assert first.status == "partial"
    assert first.items_failed and first.items_failed[0].code == "transient_error"
    assert provider.count("add_playlist_item") == len(res.items)  # writes are not auto-retried
    resumed = ps.execute_creation(app, ps.load_for_create(app, res.proposal_id))
    assert resumed.status == "completed"
    assert resumed.playlist_id == first.playlist_id
    assert provider.count("create_playlist") == 1
    assert len(provider.inserted_items) == len(res.items)


def test_crash_after_playlist_insert_resumes(app, provider, prompt, authorizer) -> None:
    authorizer.granted.append(SCOPE_WRITE)
    res = propose(app)
    p = approve_with_code(app, prompt, res.proposal_id)
    provider.inject_error("add_playlist_item", RuntimeError("process died"))
    with pytest.raises(RuntimeError):
        ps.execute_creation(app, p, "local_code")
    stored = ps.load_for_create(app, res.proposal_id)
    assert stored.state == ps.State.PARTIAL and stored.playlist_id
    done = ps.execute_creation(app, stored)
    assert done.status == "completed" and provider.count("create_playlist") == 1


def test_concurrent_reservations_exactly_one_succeeds(app) -> None:
    consume(app, units=10000 - 150)  # 150 units left
    results: list[str] = []
    barrier = threading.Barrier(2)

    def worker() -> None:
        barrier.wait()
        try:
            app.quota.reserve({"playlists.insert": 1, "playlistItems.insert": 1})  # 100 units each
            results.append("ok")
        except QuotaBudgetExceeded:
            results.append("rejected")

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["ok", "rejected"]


def test_concurrent_create_calls_single_playlist(app, provider, prompt, authorizer) -> None:
    authorizer.granted.append(SCOPE_WRITE)
    res = propose(app)
    p = approve_with_code(app, prompt, res.proposal_id)
    outcomes: list[str] = []
    barrier = threading.Barrier(2)

    def worker() -> None:
        barrier.wait()
        try:
            outcomes.append(ps.execute_creation(app, p, "local_code").status)
        except Exception as exc:  # noqa: BLE001
            outcomes.append(type(exc).__name__)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert provider.count("create_playlist") == 1
    assert "completed" in outcomes


def test_failed_workflow_keeps_consumed_releases_unused(app, provider) -> None:
    provider.inject_error("search_videos", Transient("down"))
    with pytest.raises(Transient):
        similar_videos.find_similar_videos(app, FindSimilarVideosInput(video="pdIntro0001"))
    status = app.quota.status()["buckets"]
    # seed videos.list (1 unit) + failed search.list are consumed; nothing remains reserved.
    assert status["search_calls"]["consumed"] == 1
    assert status["units"]["consumed"] == 1 + app.quota.config.cost("search.list")["units"]
    assert status["units"]["reserved"] == 0 and status["search_calls"]["reserved"] == 0


def test_read_only_token_cannot_write(app, provider, prompt, authorizer) -> None:
    authorizer.allow_write_upgrade = False
    assert authorizer.granted == [SCOPE_READ]
    res = propose(app)
    p = approve_with_code(app, prompt, res.proposal_id)
    from yt_intel_mcp.errors import WriteScopeRequired

    with pytest.raises(WriteScopeRequired):
        ps.execute_creation(app, p, "local_code")
    assert provider.write_calls == []
