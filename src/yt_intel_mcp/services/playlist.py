"""FR-5: playlist planner and proposal state machine.

    PROPOSED -> APPROVED -> CREATING -> COMPLETED | PARTIAL
    PROPOSED -> DECLINED | EXPIRED        (terminal)
    PARTIAL  -> CREATING (resume)         CREATING -> CREATING (stale lease only)

``propose_playlist`` never writes. ``execute_creation`` runs only for an APPROVED (or resumable)
proposal, reserves the full write quota atomically first, stores the playlist ID immediately after
``playlists.insert`` so a retry resumes item insertion instead of creating a second playlist, and
never auto-retries writes. Video metadata is data only and is never interpreted (FR-5.10).
"""

from __future__ import annotations

import json
import math
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from yt_intel_mcp import quota
from yt_intel_mcp.approval import MAX_CODE_ATTEMPTS, new_code_record, verify_code
from yt_intel_mcp.duration import format_duration
from yt_intel_mcp.errors import (
    AuthorizationRequired,
    ConfirmationInvalid,
    Forbidden,
    InvalidGrant,
    ProposalDeclined,
    ProposalExpired,
    ProposalInProgress,
    ProposalNotFound,
    QuotaExceeded,
    WriteScopeRequired,
    YoutubeSignupRequired,
    YTIntelError,
)
from yt_intel_mcp.ids import playlist_url
from yt_intel_mcp.schemas import (
    ConstraintCheck,
    CreatePlaylistResult,
    FailedItem,
    PlaylistItemOut,
    ProposePlaylistInput,
    ProposePlaylistResult,
    VideoMeta,
    video_from_api,
)
from yt_intel_mcp.services import AppContext, run_metered, with_quota
from yt_intel_mcp.storage import Database

PROPOSAL_TTL = timedelta(minutes=10)
CREATION_LEASE = timedelta(minutes=2)
STOPPING_ERRORS = (
    QuotaExceeded,
    InvalidGrant,
    AuthorizationRequired,
    WriteScopeRequired,
    YoutubeSignupRequired,
)

INTRO_WORDS = (
    "introduction",
    "intro ",
    "beginner",
    "basics",
    "getting started",
    "101",
    "fundamentals",
    "what is",
    "first steps",
    "crash course",
    "for dummies",
)
ADVANCED_WORDS = (
    "advanced",
    "deep dive",
    "expert",
    "masterclass",
    "in depth",
    "in-depth",
    "internals",
    "optimization",
    "optimisation",
    "pro tips",
)
ORDERING_NOTE = (
    "Best-effort order from introductory to advanced, based on title keywords only. "
    "The learning sequence is not guaranteed."
)


class State:
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    CREATING = "CREATING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"


# ==================================================================================================
# Selection
# ==================================================================================================


@dataclass
class Candidate:
    video: VideoMeta
    rank: int

    @property
    def seconds(self) -> int:
        return int(self.video.duration_seconds or 0)


def select_videos(
    candidates: list[Candidate], target: int, fill_target: float = 0.9, quantum: int = 5, max_items: int = 50
) -> list[Candidate]:
    """Fill ``target`` seconds without exceeding it, preferring relevance (lower rank).

    1. Greedy in relevance order.
    2. If below ``fill_target``: bounded subset-sum over durations rounded *up* to ``quantum`` seconds
       (so the real total can never exceed the target), visiting candidates in relevance order so
       more relevant videos claim each reachable total first. The better of the two is returned.
    """
    ordered = sorted(candidates, key=lambda c: c.rank)
    greedy: list[Candidate] = []
    total = 0
    for c in ordered:
        if len(greedy) >= max_items:
            break
        if 0 < c.seconds and total + c.seconds <= target:
            greedy.append(c)
            total += c.seconds
    if total >= fill_target * target:
        return greedy

    quantum = max(quantum, target // 2000 or 1)
    cap = target // quantum
    # reach[s] = (previous_sum, candidate_index, item_count)
    reach: dict[int, tuple[int, int, int]] = {0: (-1, -1, 0)}
    for idx, c in enumerate(ordered):
        weight = math.ceil(c.seconds / quantum)
        if weight <= 0 or weight > cap:
            continue
        for s in sorted(reach, reverse=True):
            n = s + weight
            count = reach[s][2] + 1
            if n <= cap and n not in reach and count <= max_items:
                reach[n] = (s, idx, count)
    chosen: list[Candidate] = []
    s = max(reach)
    while s:
        prev, idx, _ = reach[s]
        chosen.append(ordered[idx])
        s = prev
    dp_total = sum(c.seconds for c in chosen)
    best = chosen if dp_total > total else greedy
    return sorted(best, key=lambda c: c.rank)


def level_of(title: str | None) -> str:
    text = f" {(title or '').lower()} "
    if any(w in text for w in ADVANCED_WORDS):
        return "advanced"
    if any(w in text for w in INTRO_WORDS):
        return "intro"
    return "intermediate"


def order_intro_to_advanced(selected: list[Candidate]) -> list[Candidate]:
    order = {"intro": 0, "intermediate": 1, "advanced": 2}
    return sorted(selected, key=lambda c: (order[level_of(c.video.title)], c.rank))


def _clean_title(text: str) -> str:
    text = re.sub(r"[<>\x00-\x1f]", "", text).strip()
    return text[:150]


# ==================================================================================================
# Proposal store
# ==================================================================================================


@dataclass
class Proposal:
    id: str
    state: str
    created_at: datetime
    expires_at: datetime
    payload: dict[str, Any]
    playlist_id: str | None = None
    inserted: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    code_hash: str | None = None
    code_salt: str | None = None
    code_attempts: int = 0
    lease_until: datetime | None = None
    quota_used: dict[str, int] = field(default_factory=dict)
    result: dict[str, Any] | None = None

    @property
    def video_ids(self) -> list[str]:
        return [i["video_id"] for i in self.payload["items"]]


class ProposalStore:
    def __init__(self, db: Database, clock) -> None:
        self.db = db
        self.clock = clock

    def _now(self) -> datetime:
        return self.clock.now()

    @staticmethod
    def _row(row) -> Proposal:
        return Proposal(
            id=row["id"],
            state=row["state"],
            created_at=datetime.fromisoformat(row["created_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]),
            payload=json.loads(row["payload"]),
            playlist_id=row["playlist_id"],
            inserted=json.loads(row["inserted"]),
            failed=json.loads(row["failed"]),
            code_hash=row["code_hash"],
            code_salt=row["code_salt"],
            code_attempts=row["code_attempts"],
            lease_until=datetime.fromisoformat(row["lease_until"]) if row["lease_until"] else None,
            quota_used=json.loads(row["quota_used"]),
            result=json.loads(row["result"]) if row["result"] else None,
        )

    def create(self, payload: dict[str, Any]) -> Proposal:
        now = self._now()
        pid = uuid.uuid4().hex
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO proposals(id, state, created_at, expires_at, updated_at, payload) VALUES (?,?,?,?,?,?)",
                (
                    pid,
                    State.PROPOSED,
                    now.isoformat(),
                    (now + PROPOSAL_TTL).isoformat(),
                    now.isoformat(),
                    json.dumps(payload),
                ),
            )
        return self.get(pid)  # type: ignore[return-value]

    def get(self, pid: str) -> Proposal | None:
        with self.db.read() as conn:
            row = conn.execute("SELECT * FROM proposals WHERE id = ?", (pid,)).fetchone()
        return self._row(row) if row else None

    def update(self, pid: str, from_states: tuple[str, ...] | None = None, **values: Any) -> bool:
        """Compare-and-set update; returns False if the proposal was not in ``from_states``."""
        values["updated_at"] = self._now().isoformat()
        cols = ", ".join(f"{k} = ?" for k in values)
        params: list[Any] = [json.dumps(v) if isinstance(v, (dict, list)) else v for v in values.values()]
        sql = f"UPDATE proposals SET {cols} WHERE id = ?"  # noqa: S608 - column names are internal
        params.append(pid)
        if from_states:
            sql += f" AND state IN ({','.join('?' * len(from_states))})"
            params.extend(from_states)
        with self.db.transaction() as conn:
            return conn.execute(sql, params).rowcount == 1

    def expire_if_needed(self, p: Proposal) -> Proposal:
        if p.state in (State.PROPOSED, State.APPROVED) and self._now() >= p.expires_at:
            self.update(p.id, (State.PROPOSED, State.APPROVED), state=State.EXPIRED, code_hash=None, code_salt=None)
            return self.get(p.id)  # type: ignore[return-value]
        return p

    def claim(self, pid: str) -> bool:
        now = self._now()
        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE proposals SET state = ?, lease_until = ?, updated_at = ? WHERE id = ? AND "
                "(state IN (?, ?) OR (state = ? AND (lease_until IS NULL OR lease_until < ?)))",
                (
                    State.CREATING,
                    (now + CREATION_LEASE).isoformat(),
                    now.isoformat(),
                    pid,
                    State.APPROVED,
                    State.PARTIAL,
                    State.CREATING,
                    now.isoformat(),
                ),
            )
            return cur.rowcount == 1

    def add_inserted(self, pid: str, video_id: str) -> None:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT inserted, failed FROM proposals WHERE id = ?", (pid,)).fetchone()
            inserted = json.loads(row["inserted"])
            failed = json.loads(row["failed"])
            if video_id not in inserted:
                inserted.append(video_id)
            failed.pop(video_id, None)
            conn.execute(
                "UPDATE proposals SET inserted = ?, failed = ? WHERE id = ?",
                (json.dumps(inserted), json.dumps(failed), pid),
            )


# ==================================================================================================
# Summaries
# ==================================================================================================


def _safe(text: str | None, limit: int = 100) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text or "(no title)").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def proposal_summary(p: Proposal, units: int | None = None) -> str:
    pl = p.payload
    lines = [
        f"Create a new {pl['privacy'].upper()} YouTube playlist?",
        f"Title: {_safe(pl['title'], 150)}",
        f"Videos: {len(pl['items'])}, total {format_duration(pl['total_duration_seconds'])}",
    ]
    for item in pl["items"]:
        lines.append(
            f"  {item['position']}. {_safe(item['title'])} — {_safe(item['channel_title'], 60)} "
            f"({item['duration_text']})"
        )
    if units is not None:
        lines.append(f"Estimated quota: {units} units")
    lines.append(f"Proposal {p.id} (expires {p.expires_at.isoformat(timespec='minutes')})")
    lines.append("Existing videos and playlists are never modified or deleted.")
    return "\n".join(lines)


# ==================================================================================================
# propose_playlist
# ==================================================================================================


def plan(app: AppContext) -> tuple[dict[str, int], dict[str, int]]:
    pages = int(app.retrieval("playlist")["search_pages"])
    return {"search.list": pages, "videos.list": pages}, {"search.list": 1, "videos.list": 1}


def propose_playlist(app: AppContext, inp: ProposePlaylistInput) -> ProposePlaylistResult:
    r = app.retrieval("playlist")
    target = int(round(inp.total_duration_min * 60))
    max_s = int(round(inp.max_video_duration_min * 60))
    min_s = int(round(inp.min_video_duration_min * 60)) if inp.min_video_duration_min else None
    full, minimum = plan(app)
    store = ProposalStore(app.db, app.clock)

    def work() -> ProposePlaylistResult:
        filters: dict[str, Any] = {
            "relevanceLanguage": inp.language,
            "maxResults": int(r["results_per_page"]),
        }
        if max_s < 240:
            filters["videoDuration"] = "short"
        elif min_s and min_s > 1200:
            filters["videoDuration"] = "long"
        elif min_s and min_s >= 240 and max_s <= 1200:
            filters["videoDuration"] = "medium"
        order: list[str] = []
        metas: dict[str, VideoMeta] = {}
        excluded: Counter[str] = Counter()
        notes_stop = False
        token: str | None = None
        for _ in range(int(r["search_pages"])):
            if not quota.can_afford("search.list", keep={"videos.list": 1}):
                notes_stop = True
                break
            resp = app.provider.search_videos(inp.topic, filters, token)
            new_ids = []
            for item in resp.get("items", []):
                if item["video_id"] in metas or item["video_id"] in order:
                    excluded["duplicate"] += 1
                    continue
                order.append(item["video_id"])
                new_ids.append(item["video_id"])
            if new_ids:
                if not quota.can_afford("videos.list"):
                    notes_stop = True
                    break
                for raw in app.provider.get_videos(new_ids):
                    metas[raw["id"]] = video_from_api(raw)
            eligible_seconds = sum(
                m.duration_seconds or 0
                for m in metas.values()
                if m.available and m.duration_seconds and m.duration_seconds <= max_s
            )
            token = resp.get("next_page_token")
            if not token or eligible_seconds >= 3 * target:
                break

        unknown: Counter[str] = Counter()
        seen_titles: set[tuple[str, str]] = set()
        candidates: list[Candidate] = []
        for rank, vid in enumerate(order):
            m = metas.get(vid)
            if m is None:
                excluded["deleted_or_private"] += 1
            elif not m.available:
                excluded["private_or_unavailable"] += 1
            elif m.duration_seconds is None:
                excluded["unknown_duration"] += 1
                unknown["duration"] += 1
            elif m.duration_seconds > max_s:
                excluded["longer_than_max"] += 1
            elif min_s and m.duration_seconds < min_s:
                excluded["shorter_than_min"] += 1
            elif m.language is None:
                excluded["unknown_language"] += 1
                unknown["language"] += 1
            elif m.language != inp.language:
                excluded["language_mismatch"] += 1
            else:
                key = (re.sub(r"\W+", " ", (m.title or "").lower()).strip(), m.channel_id or "")
                if key in seen_titles:
                    excluded["duplicate"] += 1
                    continue
                seen_titles.add(key)
                candidates.append(Candidate(m, rank))

        selected = select_videos(
            candidates,
            target,
            float(r.get("fill_target", 0.9)),
            int(r.get("duration_quantum_seconds", 5)),
            int(r.get("max_items", 50)),
        )
        title = _clean_title(f"{inp.topic} — curated playlist")
        stop_note = " Search stopped early because the reserved quota was used up." if notes_stop else ""
        if not selected:
            return ProposePlaylistResult(
                status="no_candidates",
                summary="No eligible videos matched the topic and constraints, so no proposal was created." + stop_note,
                proposal_id=None,
                title=title,
                privacy=inp.privacy,
                items=[],
                total_duration_seconds=0,
                target_duration_seconds=target,
                fill_ratio=0.0,
                constraints_checked=[],
                excluded=dict(excluded),
                unknown_metadata=dict(unknown),
                unmet_constraints=["No video satisfied all constraints."],
                shortfall_seconds=target,
                estimated_write_quota={},
                ordering_note=ORDERING_NOTE,
                expires_at=None,
                next_step="Try a broader topic, a longer maximum video duration or another language.",
            )

        ordered = order_intro_to_advanced(selected)
        total = sum(c.seconds for c in ordered)
        fill = round(total / target, 4)
        fill_goal = float(r.get("fill_target", 0.9))
        items = [
            PlaylistItemOut(
                position=i + 1,
                video_id=c.video.video_id,
                title=c.video.title,
                channel_title=c.video.channel_title,
                duration_seconds=c.seconds,
                duration_text=format_duration(c.seconds),
                url=c.video.url,
                level=level_of(c.video.title),
            )
            for i, c in enumerate(ordered)
        ]
        checks = [
            ConstraintCheck(
                name="total_duration_not_exceeded",
                satisfied=total <= target,
                detail=f"{format_duration(total)} of {format_duration(target)}",
            ),
            ConstraintCheck(
                name="max_video_duration",
                satisfied=all(c.seconds <= max_s for c in ordered),
                detail=f"every video is at most {format_duration(max_s)}",
            ),
            ConstraintCheck(
                name="language",
                satisfied=all(c.video.language == inp.language for c in ordered),
                detail=f"every video's audio/default language is '{inp.language}'",
            ),
            ConstraintCheck(
                name="fill_target",
                satisfied=fill >= fill_goal,
                detail=f"{fill:.0%} of the requested duration (goal at least {fill_goal:.0%})",
            ),
            ConstraintCheck(name="no_duplicates", satisfied=True, detail="each video appears once"),
            ConstraintCheck(name="privacy", satisfied=True, detail=f"playlist will be {inp.privacy}"),
        ]
        if min_s:
            checks.insert(
                2,
                ConstraintCheck(
                    name="min_video_duration",
                    satisfied=all(c.seconds >= min_s for c in ordered),
                    detail=f"every video is at least {format_duration(min_s)}",
                ),
            )
        unmet: list[str] = []
        shortfall = max(0, target - total)
        if fill < fill_goal:
            unmet.append(
                f"Only {fill:.0%} of the requested {format_duration(target)} could be filled "
                f"(shortfall {format_duration(shortfall)}): not enough eligible videos matched the constraints."
            )
            if len(ordered) >= int(r.get("max_items", 50)):
                unmet.append(f"The playlist reached the maximum of {r.get('max_items', 50)} items.")
        write_quota = app.quota.estimate({"playlists.insert": 1, "playlistItems.insert": len(items)})
        write_quota = {k: v for k, v in write_quota.items() if v}
        payload = {
            "topic": inp.topic,
            "title": title,
            "description": (
                f"Playlist about {inp.topic[:80]} ({format_duration(total)}), proposed by YouTube Video "
                "Intelligence MCP and approved by the account owner."
            ),
            "privacy": inp.privacy,
            "language": inp.language,
            "items": [i.model_dump() for i in items],
            "total_duration_seconds": total,
            "target_duration_seconds": target,
        }
        proposal = store.create(payload)
        return ProposePlaylistResult(
            status="proposed",
            summary=(
                f"Proposed a {inp.privacy} playlist of {len(items)} videos totalling {format_duration(total)} "
                f"({fill:.0%} of {format_duration(target)}). Nothing has been written to YouTube." + stop_note
            ),
            proposal_id=proposal.id,
            title=title,
            privacy=inp.privacy,
            items=items,
            total_duration_seconds=total,
            target_duration_seconds=target,
            fill_ratio=fill,
            constraints_checked=checks,
            excluded=dict(excluded),
            unknown_metadata=dict(unknown),
            unmet_constraints=unmet,
            shortfall_seconds=shortfall,
            estimated_write_quota=write_quota,
            ordering_note=ORDERING_NOTE,
            expires_at=proposal.expires_at.isoformat(),
            next_step=(
                "Show this proposal to the user. Only if they want it, call create_playlist with this "
                "proposal_id; the server then asks the user to approve it directly."
            ),
        )

    result, used = run_metered(app, "propose_playlist", full, work, min_plan=minimum)
    return with_quota(result, used)


# ==================================================================================================
# create_playlist steps
# ==================================================================================================


def load_for_create(app: AppContext, proposal_id: str) -> Proposal:
    store = ProposalStore(app.db, app.clock)
    p = store.get(proposal_id)
    if p is None:
        raise ProposalNotFound("No proposal with this ID exists.")
    p = store.expire_if_needed(p)
    if p.state == State.EXPIRED:
        raise ProposalExpired("This proposal has expired; nothing was created.")
    if p.state == State.DECLINED:
        raise ProposalDeclined("This proposal was declined; nothing was created.")
    return p


def write_units(app: AppContext, p: Proposal) -> int:
    remaining = len([v for v in p.video_ids if v not in p.inserted])
    plan_ = {"playlistItems.insert": remaining, "playlists.insert": 0 if p.playlist_id else 1}
    return app.quota.estimate(plan_).get("units", 0)


def existing_result(p: Proposal) -> CreatePlaylistResult:
    data = dict(p.result or {})
    data["status"] = "already_completed"
    data["summary"] = "This proposal was already completed. No new playlist was created. " + data.get("summary", "")
    return CreatePlaylistResult(**data)


def issue_code(app: AppContext, p: Proposal) -> CreatePlaylistResult:
    """Local approval: create a fresh single-use code and show it ONLY on the local prompt."""
    store = ProposalStore(app.db, app.clock)
    code, salt, digest = new_code_record()
    if not store.update(p.id, (State.PROPOSED,), code_hash=digest, code_salt=salt, code_attempts=0):
        raise ProposalInProgress("The proposal changed state; call create_playlist again.")
    app.approval_prompt.show(p.id, proposal_summary(p, write_units(app, p)), code, p.expires_at)
    del code
    return CreatePlaylistResult(
        status="approval_pending",
        summary=(
            "Approval is needed. A local approval page has opened in the browser on the user's computer, "
            "showing this proposal and a one-time confirmation code. Nothing has been written to YouTube."
        ),
        proposal_id=p.id,
        approval_mechanism="local_code",
        items_total=len(p.video_ids),
        expires_at=p.expires_at.isoformat(),
        writes_to_youtube=False,
        next_step=(
            "Ask the user to review the approval page. If they approve, they will tell you the code; then "
            "call create_playlist again with proposal_id and confirmation_code. Never guess or invent a code."
        ),
    )


def confirm_code(app: AppContext, p: Proposal, code: str) -> Proposal:
    store = ProposalStore(app.db, app.clock)
    if p.state != State.PROPOSED or not p.code_hash:
        raise ConfirmationInvalid(
            "No confirmation code is pending for this proposal.",
            "Call create_playlist with only the proposal_id to open the local approval page.",
        )
    if verify_code(code, p.code_salt, p.code_hash):
        # Single use: the hash is cleared in the same compare-and-set that approves the proposal.
        with store.db.transaction() as conn:
            ok = (
                conn.execute(
                    "UPDATE proposals SET state = ?, code_hash = NULL, code_salt = NULL, updated_at = ? "
                    "WHERE id = ? AND state = ? AND code_hash = ?",
                    (State.APPROVED, app.clock.now().isoformat(), p.id, State.PROPOSED, p.code_hash),
                ).rowcount
                == 1
            )
        if ok:
            return store.get(p.id)  # type: ignore[return-value]
    attempts = p.code_attempts + 1
    if attempts >= MAX_CODE_ATTEMPTS:
        store.update(p.id, (State.PROPOSED,), code_hash=None, code_salt=None, code_attempts=attempts)
        raise ConfirmationInvalid(
            "The confirmation code is wrong. Too many attempts: the code is no longer valid.",
            "Call create_playlist with only the proposal_id to show a new code on the local approval page.",
        )
    store.update(p.id, (State.PROPOSED,), code_attempts=attempts)
    raise ConfirmationInvalid("The confirmation code is wrong or was already used. No playlist was created.")


def approve(app: AppContext, p: Proposal) -> Proposal:
    store = ProposalStore(app.db, app.clock)
    if not store.update(p.id, (State.PROPOSED,), state=State.APPROVED, code_hash=None, code_salt=None):
        raise ProposalInProgress("The proposal changed state during approval; nothing was created.")
    return store.get(p.id)  # type: ignore[return-value]


def decline(app: AppContext, p: Proposal) -> None:
    ProposalStore(app.db, app.clock).update(
        p.id, (State.PROPOSED,), state=State.DECLINED, code_hash=None, code_salt=None
    )


def execute_creation(app: AppContext, p: Proposal, mechanism: str | None = None) -> CreatePlaylistResult:
    store = ProposalStore(app.db, app.clock)
    if p.state not in (State.APPROVED, State.PARTIAL, State.CREATING):
        raise ProposalInProgress("The proposal is not approved.")
    # Incremental authorisation: the write scope is requested only now (FR-7).
    if not app.authorizer.has_scope(write=True):
        app.authorizer.authorize(write=True)
    remaining = [v for v in p.video_ids if v not in p.inserted]
    plan_ = {"playlistItems.insert": len(remaining)}
    if not p.playlist_id:
        plan_["playlists.insert"] = 1
    reservation = app.quota.reserve(plan_, label=f"create_playlist:{p.id}")  # atomic, all-or-nothing
    if not store.claim(p.id):
        reservation.release_unused()
        current = store.get(p.id)
        if current and current.state == State.COMPLETED:
            return existing_result(current)
        raise ProposalInProgress("Playlist creation for this proposal is already running.")

    playlist_id = p.playlist_id
    privacy = (p.result or {}).get("privacy") or p.payload["privacy"]
    failed: dict[str, str] = {}
    try:
        with quota.active(reservation):
            if not playlist_id:
                try:
                    created = app.provider.create_playlist(
                        p.payload["title"], p.payload["description"], p.payload["privacy"]
                    )
                except YTIntelError:
                    store.update(p.id, (State.CREATING,), state=State.APPROVED, lease_until=None)
                    raise
                playlist_id = created["playlist_id"]
                privacy = created.get("privacy_status") or p.payload["privacy"]
                # Stored immediately so a retry resumes instead of creating a second playlist (FR-5.9).
                store.update(p.id, (State.CREATING,), playlist_id=playlist_id)
            for vid in remaining:
                try:
                    app.provider.add_playlist_item(playlist_id, vid)
                except STOPPING_ERRORS as exc:
                    failed[vid] = exc.code
                    break
                except (Forbidden, YTIntelError) as exc:
                    failed[vid] = exc.code
                    continue
                store.add_inserted(p.id, vid)
    except BaseException:
        current = store.get(p.id)
        if current and current.state == State.CREATING:
            store.update(
                p.id,
                (State.CREATING,),
                state=State.PARTIAL if current.playlist_id else State.APPROVED,
                lease_until=None,
            )
        reservation.release_unused()
        raise
    used = reservation.release_unused()

    current = store.get(p.id)
    assert current is not None
    total_used = dict(Counter(current.quota_used) + Counter(used))
    done = len(current.inserted)
    total = len(current.video_ids)
    status = "completed" if done == total else "partial"
    result = CreatePlaylistResult(
        status=status,
        summary=(
            f'Created the {privacy} playlist "{p.payload["title"]}" with {done} of {total} videos.'
            if status == "completed"
            else f'Playlist "{p.payload["title"]}" was created but only {done} of {total} videos were added.'
        ),
        proposal_id=p.id,
        approval_mechanism=mechanism or (p.result or {}).get("approval_mechanism"),
        playlist_id=playlist_id,
        playlist_url=playlist_url(playlist_id),
        privacy=privacy,
        items_inserted=done,
        items_total=total,
        items_failed=[FailedItem(video_id=v, code=c) for v, c in failed.items()],
        quota_used=total_used,
        next_step=None
        if status == "completed"
        else (
            "Call create_playlist again with the same proposal_id to retry the missing videos. "
            "The existing playlist is reused; no duplicate is created."
        ),
    )
    store.update(
        p.id,
        (State.CREATING,),
        state=State.COMPLETED if status == "completed" else State.PARTIAL,
        failed=failed,
        quota_used=total_used,
        lease_until=None,
        result=result.model_dump(),
    )
    return result


def simple_result(p: Proposal, status: str, summary: str, mechanism: str | None) -> CreatePlaylistResult:
    return CreatePlaylistResult(
        status=status,
        summary=summary,
        proposal_id=p.id,
        approval_mechanism=mechanism,
        items_total=len(p.video_ids),
        expires_at=p.expires_at.isoformat(),
        writes_to_youtube=False,
        next_step="Nothing was written to YouTube."
        if status != "cancelled"
        else ("Nothing was written. Call create_playlist again before the proposal expires if the user wants it."),
    )
