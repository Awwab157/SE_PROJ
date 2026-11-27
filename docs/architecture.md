# Architecture and design (SE-2)

System design of the **YouTube Video Intelligence MCP Server**, release 1.0. This file is the source of the design PDF
[`docs/design.pdf`](design.pdf) (rebuild with `python scripts/build_design_pdf.py` after every change here or in
`docs/adr/`). Decisions are recorded as ADRs in [`docs/adr/`](adr/); the API reference is [`docs/api.md`](api.md).

## 1. Goals and constraints
- Let an AI client discover, analyse and curate YouTube videos for **one authorised user** (BR-1): similar videos
  (FR-1), similar channels (FR-2), recommendations (FR-3), engagement analysis (FR-4) and playlist creation (FR-5).
- **Official YouTube Data API v3 only.** No scraping, no transcripts, no watch history, no related-videos endpoint
  (it does not exist): similarity is computed locally from metadata (ADR 0004).
- **Quota is a hard limit** (10,000 units/day, 100 searches/day by default): every workflow reserves its worst-case
  cost before the first call (ADR 0003).
- **The only write is creating a new playlist**, and only after explicit approval from the human (ADR 0002). Existing
  videos and playlists are never modified or deleted.
- **All YouTube text is untrusted data**, never instructions (prompt-injection safe).
- Local desktop tool: stdio transport, Python 3.11+, official MCP SDK (ADR 0001); state outside the repository (ADR 0005).

## 2. System context
```mermaid
flowchart LR
    user(["User"])
    client["AI client<br/>Claude / ChatGPT / Gemini"]
    server["yt-intel-mcp<br/>MCP server (local process)"]
    google[("Google OAuth 2.0")]
    yt[("YouTube Data API v3")]
    browser["System browser<br/>sign-in, local approval page"]
    keychain[("OS keychain")]
    state[("state.db<br/>~/.yt-intel-mcp")]
    user -- chat --> client
    client -- "MCP over stdio<br/>tools, resources, prompts" --> server
    server -- HTTPS --> yt
    server -- "PKCE, loopback" --> google
    server -- opens --> browser
    user -- "consent, approval code" --> browser
    server --> keychain
    server --> state
```

## 3. Deployment
```mermaid
flowchart TB
    subgraph pc["User's computer"]
        subgraph clientproc["AI client process"]
            cl["MCP client"]
        end
        subgraph srvproc["python -m yt_intel_mcp (child process, stdio)"]
            srv["MCPServer"]
            http["Loopback HTTP 127.0.0.1<br/>OAuth redirect + approval page"]
        end
        db[("~/.yt-intel-mcp/state.db<br/>dir 0700, file 0600")]
        kc[("OS keychain<br/>fallback: encrypted file 0600")]
        cfg["config/quota.yaml<br/>config/similarity.yaml"]
        skills["skills/*/SKILL.md"]
    end
    cl <-- "stdin/stdout JSON-RPC" --> srv
    srv --> db
    srv --> kc
    srv --> cfg
    srv --> skills
    srv -- HTTPS --> api[("googleapis.com")]
```
The client starts the server as a child process (configuration snippet in `docs/user-guide.md`). Logs go to stderr,
because stdout is the transport. There is no network listener except short-lived loopback servers for the OAuth
redirect and the approval page.

## 4. Component view
```mermaid
flowchart TB
    client["MCP client"] -- "stdio JSON-RPC" --> server["server.py<br/>MCPServer: 9 tools, 3 resources, 1 prompt"]
    server --> support
    subgraph support["server support"]
        direction TB
        schemas["schemas.py<br/>pydantic input/output models"]
        approval["approval.py<br/>elicitation / local code page"]
        skillfile["skills/video-to-playlist/SKILL.md<br/>served as MCP prompt"]
        logs["logging_utils.py<br/>redacted stderr logs"]
        schemas ~~~ approval ~~~ skillfile ~~~ logs
    end
    server --> services
    subgraph services["services/"]
        direction TB
        sv["similar_videos"]
        sc["similar_channels"]
        rec["recommendations"]
        eng["engagement"]
        pl["playlist"]
        sv ~~~ sc ~~~ rec ~~~ eng ~~~ pl
    end
    services --> sim["similarity.py<br/>TF-IDF + weighted score"]
    services --> quota["quota.py<br/>reserve / charge / release"]
    services --> cache["cache.py<br/>CachingProvider"]
    cache --> provider{{"providers/base.py<br/>YouTubeProvider"}}
    provider --> live["providers/live.py<br/>only googleapiclient import"]
    provider --> fixture["providers/fixture.py<br/>tests, local-check, --sample"]
    live --> yt[("YouTube Data API v3")]
    live --> auth["auth.py<br/>OAuth PKCE, keyring"]
    quota & cache & pl --> db[("state.db (SQLite)")]
    auth --> keychain[("OS keychain")]
```

| Module | Responsibility | Requirements |
|---|---|---|
| `server.py` | Builds the app (`build_app`), registers tools, resources and the skill prompt, maps results and errors to MCP | FR-8, UI-1, UI-3, NFR-19 |
| `schemas.py` | Pydantic models for every tool input and output; normalises API resources (`video_from_api`, `channel_from_api`) | FR-8.3, FR-1.2 |
| `services/similar_videos.py` | FR-1 workflow: seed lookup, candidate search, scoring | FR-1 |
| `services/similar_channels.py` | FR-2 workflow: channel resolution (ID, @handle, /channel/, /user/, /c/), content-first ranking | FR-2 |
| `services/recommendations.py` | FR-3: interest profile from likes, subscriptions and playlists; candidate search; signals | FR-3 |
| `services/engagement.py` | FR-4: top channels and categories, trends, duration buckets, period comparison, computed locally | FR-4 |
| `services/playlist.py` | FR-5: planner (topic search or `candidate_video_ids`), proposal store, approval state machine, idempotent creation | FR-5 |
| `similarity.py` | Tokenising, TF-IDF cosine, weighted video score, channel ranking, explanations | FR-1.4, FR-2 |
| `quota.py` | Cost table, plans, atomic reservation, per-call charging, ledger, Pacific-time reset | FR-6, TQ-6 |
| `cache.py` | `CachingProvider`: 24 h serve, 7 d purge, never caches writes | FR-6.6, NFR-11 |
| `providers/base.py` | `YouTubeProvider` interface: 10 reads + 2 writes; no update, delete or history methods | SE-6, NFR-5 |
| `providers/live.py` | Google API client, error mapping, bounded retries for reads only | NFR-13, NFR-15 |
| `providers/fixture.py` | Synthetic JSON fixtures, call log, error injection | TQ-5 |
| `auth.py` | Installed-app OAuth (loopback, state, PKCE), incremental write scope, token storage, revocation | FR-7 |
| `approval.py` | Elicitation and the local one-time-code page | FR-5.6 |
| `ids.py`, `duration.py` | URL/ID parsing, ISO 8601 durations | FR-1.1, FR-2.1, FR-4.5 |
| `errors.py` | `YTIntelError` hierarchy with code, cause, next step | UI-3 |
| `storage.py`, `clock.py`, `config.py`, `logging_utils.py` | SQLite state outside the repo, injectable clock, YAML config, redacted logging with per-tool timing | NFR-10, NFR-1 |

## 5. Provider abstraction
```mermaid
classDiagram
    class YouTubeProvider {
        <<abstract>>
        +get_videos(ids)
        +search_videos(query, filters, page_token)
        +search_channels(query, max_results)
        +get_channels(ids, for_handle, for_username)
        +list_channel_uploads(channel_id, max)
        +list_liked_videos(max_items)
        +list_subscriptions(max_items)
        +list_playlists(max_items)
        +list_playlist_items(playlist_id, max_items)
        +list_video_categories(region)
        +create_playlist(title, description, privacy)
        +add_playlist_item(playlist_id, video_id)
    }
    class LiveProvider {
        -authorizer
        -_execute(api_method, request, write)
        +map_http_error()
    }
    class FixtureProvider {
        +calls
        +write_calls
        +inject_error()
    }
    class CachingProvider {
        -inner: YouTubeProvider
        -cache: Cache
    }
    YouTubeProvider <|-- LiveProvider
    YouTubeProvider <|-- FixtureProvider
    YouTubeProvider <|-- CachingProvider
    CachingProvider o-- YouTubeProvider : wraps
```
Services only see `CachingProvider`, so tests swap the live provider for fixtures without touching service code.
The interface has no method that could modify or delete existing content or read viewing history.

## 6. MCP surface
| Kind | Name | Writes to YouTube | Purpose |
|---|---|---|---|
| Tool | `find_similar_videos` | no | FR-1 ranked similar videos with scores and explanations; returns seed metadata for the skill's summary |
| Tool | `find_similar_channels` | no | FR-2 ranked similar channels; ambiguous `/c/` URLs return candidates |
| Tool | `recommend_videos` | no | FR-3 recommendations with contributing signals |
| Tool | `analyze_engagement` | no | FR-4 analysis for a period, optional comparison period |
| Tool | `propose_playlist` | no | FR-5 plan from a topic or from `candidate_video_ids`; returns a proposal valid 10 minutes |
| Tool | `create_playlist` | **yes** | FR-5 creation of one new playlist after user approval |
| Tool | `start_authorization`, `revoke_authorization`, `clear_cache` | no | FR-7 sign-in, revocation, local data deletion |
| Resource | `quota://status`, `config://server`, `proposal://{id}` | no | Quota per bucket, non-secret config, proposal view (no codes) |
| Prompt | `video-to-playlist` | no (the prompt itself) | Agent Skill SK-1 exposed through the server; text is `skills/video-to-playlist/SKILL.md` |

Every tool result has structured content plus a short summary text (UI-1). Errors are `isError` results with
`code`, `cause` and `next_step` (UI-3). Descriptions state whether a tool writes (NFR-19). Agent Skills are not
registered as tools or resources (FR-8.5); they are served as prompts.

## 7. Key workflows

### 7.1 Read workflow with quota (FR-1; FR-2 to FR-4 follow the same pattern)
```mermaid
sequenceDiagram
    participant C as MCP client
    participant S as server.py
    participant V as similar_videos
    participant Q as QuotaManager
    participant P as CachingProvider
    participant Y as YouTube API
    C->>S: find_similar_videos(video, limit)
    S->>S: validate input (pydantic, parse_video_id)
    S->>V: run in worker thread
    V->>Q: reserve(full plan, min plan)
    alt minimum plan does not fit
        Q-->>C: quota_budget_exceeded (cost, limit, remaining), zero API calls
    end
    V->>P: get_videos([seed])
    P->>Y: videos.list (charge before call)
    V->>P: search_videos x N, list_channel_uploads
    Note over V,P: each optional call checks can_afford first
    V->>P: get_videos(candidates)
    V->>V: score_videos (TF-IDF + weights)
    V->>Q: release_unused()
    V-->>S: result + quota_used
    S-->>C: summary text + structured content
```

### 7.2 Playlist proposal and approval (FR-5)
```mermaid
sequenceDiagram
    actor U as User
    participant C as MCP client / model
    participant S as Server
    participant Q as Quota ledger
    participant Y as YouTube API
    C->>S: propose_playlist(topic, durations, language[, candidate_video_ids])
    S->>Q: reserve(search + videos.list, or 1 videos.list for candidates)
    S->>Y: search.list, videos.list (reads only)
    S-->>C: proposal (id, items, checks, exclusions, est. quota), nothing written
    C->>U: show proposal
    U->>C: "create it"
    C->>S: create_playlist(proposal_id)
    alt client supports elicitation
        S->>C: elicitation (exact proposal summary)
        C->>U: dialog
        U-->>C: accept / decline / cancel
        C-->>S: result
    else local approval
        S->>U: page on 127.0.0.1 (summary + one-time code)
        S-->>C: approval_pending (no code)
        U->>C: types code
        C->>S: create_playlist(proposal_id, confirmation_code)
        S->>S: verify salted hash, single use
    else neither
        S-->>C: approval_unavailable (fail closed)
    end
    S->>S: incremental OAuth for write scope (first time)
    S->>Q: reserve 50 + 50 x n units (atomic, all or nothing)
    S->>Y: playlists.insert
    S->>S: store playlist_id immediately
    loop each video
        S->>Y: playlistItems.insert (never auto-retried)
    end
    S-->>C: URL, completed / partial, privacy, quota used
```

### 7.3 Agent Skill `video-to-playlist` (SK-1)
```mermaid
sequenceDiagram
    actor U as User
    participant C as MCP client / model
    participant S as Server
    U->>C: pick prompt video-to-playlist(video)
    C->>S: prompts/get video-to-playlist
    S-->>C: SKILL.md steps + validated video ID
    C->>S: find_similar_videos(video, 25)
    S-->>C: seed metadata + ranked similar videos
    C->>U: 1. metadata-based summary, 2. similar videos
    C->>S: propose_playlist(..., candidate_video_ids = similar IDs)
    S-->>C: proposal built only from those videos
    C->>U: 3. proposal, "Create this playlist?"
    U->>C: yes
    C->>S: create_playlist(proposal_id)
    Note over S,U: approval exactly as in 7.2
    S-->>C: playlist URL, quota used
    C->>U: 4. created playlist, 5. short analysis (duration, channels, categories, levels)
```

### 7.4 Authorisation (FR-7)
```mermaid
sequenceDiagram
    actor U as User
    participant S as Server (auth.py)
    participant B as Browser
    participant G as Google OAuth
    participant K as Keychain
    S->>S: create state + PKCE verifier/challenge (S256)
    S->>B: open consent URL (scope youtube.readonly)
    U->>B: sign in, consent
    B->>S: redirect to 127.0.0.1 with code + state
    S->>S: check state
    S->>G: exchange code + verifier
    G-->>S: access + refresh token
    S->>K: store token
    Note over S,G: first create_playlist: same flow with scope youtube and include_granted_scopes
    Note over S,G: invalid_grant (e.g. 7-day Testing-mode expiry) -> reauthorization_required -> start_authorization
```

## 8. Proposal state machine
```mermaid
stateDiagram-v2
    [*] --> PROPOSED: propose_playlist
    PROPOSED --> APPROVED: elicitation accept / valid code
    PROPOSED --> DECLINED: elicitation decline
    PROPOSED --> EXPIRED: 10 min elapsed
    APPROVED --> EXPIRED: 10 min elapsed before creation
    APPROVED --> CREATING: claim (quota reserved)
    CREATING --> APPROVED: playlists.insert failed (nothing created)
    CREATING --> COMPLETED: all items inserted
    CREATING --> PARTIAL: some items failed / crash after insert
    PARTIAL --> CREATING: retry resumes with stored playlist_id
    COMPLETED --> COMPLETED: repeat returns existing result
    DECLINED --> [*]
    EXPIRED --> [*]
    COMPLETED --> [*]
```

## 9. Data model (state.db)
```mermaid
erDiagram
    CACHE {
        text key PK "sha256(method, args)"
        text method
        text value "JSON"
        real fetched_at
    }
    QUOTA_LEDGER {
        text day PK "Pacific date"
        text bucket PK "search_calls or units"
        int consumed
        int reserved
    }
    RESERVATIONS {
        text id PK
        text day
        text label
        text created_at
        text status "active or closed"
        text remaining "JSON per bucket"
        text consumed "JSON per bucket"
    }
    QUOTA_EVENTS {
        int id PK
        text ts
        text reservation_id FK
        text api_method
        text cost "JSON"
    }
    PROPOSALS {
        text id PK
        text state
        text created_at
        text expires_at
        text payload "title, privacy, items"
        text playlist_id
        text inserted "JSON list"
        text failed "JSON map"
        text code_hash "PBKDF2, never the code"
        text code_salt
        int code_attempts
        text lease_until
        text quota_used
        text result
    }
    RESERVATIONS ||--o{ QUOTA_EVENTS : records
    QUOTA_LEDGER ||--o{ RESERVATIONS : "aggregates per day"
```

## 10. Similarity design (ADR 0004)
- **Video document:** title twice, tags, description (max 2,000 characters); URLs, English and domain stop words removed.
- **Video score** = 0.55 text cosine + 0.15 shared tags (Jaccard) + 0.10 same category + 0.05 same channel + 0.10
  duration closeness + 0.05 language match (`config/similarity.yaml`). Ties are broken by video ID; each result explains
  its shared terms, tags and matching signals.
- **Channels:** profile = channel title and description plus recent upload titles and descriptions. Ranked by content
  similarity at fixed precision; subscriber closeness, upload cadence and language only break ties.
- **Recommendations:** an interest profile (weighted terms from likes, playlist items and subscriptions) is compared
  with candidates by TF-IDF cosine (0.6) plus liked-channel (0.2), subscribed (0.1) and category (0.1) signals.
- **Playlist selection:** greedy fill by relevance, then a bounded subset-sum if the fill is below 90 %; durations are
  rounded up, so the total never exceeds the target. Items are ordered intro, intermediate, advanced by title keywords.

## 11. Quota design (ADR 0003)
| Method | `search_calls` | `units` |
|---|---|---|
| `search.list` | 1 | 100 |
| `videos.list`, `channels.list`, `playlists.list`, `playlistItems.list`, `subscriptions.list`, `videoCategories.list` | 0 | 1 |
| `playlists.insert`, `playlistItems.insert` | 0 | 50 |

Services reserve a worst-case **plan** before the first call (`BEGIN IMMEDIATE` across buckets). A minimum plan must
fit, otherwise the request fails with `quota_budget_exceeded` and zero API calls (TQ-6). Providers charge before every
HTTP attempt; unused reservation is released. `quotaExceeded` from YouTube is never retried and marks the day as
exhausted. Cache hits cost nothing.

## 12. Error model
| Code | Raised when | Next step for the user |
|---|---|---|
| `invalid_input` | Schema or ID validation fails | Correct the input |
| `not_found` | Private, deleted or unknown video/channel | Check the ID |
| `quota_budget_exceeded` | Reservation does not fit the remaining budget | Wait for the Pacific-time reset or lower the limit |
| `quota_exceeded` | YouTube reports quota exhaustion | Wait for reset |
| `rate_limited`, `transient_error` | 429 / 5xx after bounded read retries | Retry later |
| `reauthorization_required` | `invalid_grant`, revoked or expired token | `start_authorization` |
| `authorization_required`, `write_scope_required` | No token / read-only token for a write | Sign in / approve write scope |
| `youtube_signup_required` | Account has no YouTube channel | Create a channel |
| `proposal_not_found`, `proposal_expired`, `proposal_declined`, `proposal_in_progress` | Proposal state does not allow the action | Propose again / wait |
| `confirmation_invalid`, `approval_unavailable` | Wrong or reused code / no safe approval channel | Use the approval page / a client with elicitation |
| `internal_error` | Anything unexpected | Retry; check the redacted log |

Library messages and stack traces are never returned to the client.

## 13. Security design
| Threat | Control |
|---|---|
| Model writes without the user's consent (incl. prompt injection in titles/descriptions) | Only `create_playlist` writes; approval comes from elicitation or a code shown outside the chat; codes are single use, salted PBKDF2 hashes, 3 attempts; fail closed |
| Over-broad OAuth access | `youtube.readonly` for reads; `youtube` requested only at first playlist creation; PKCE + `state`, loopback redirect |
| Token or secret leakage | Tokens in the OS keychain; state directory outside the repo (refused inside it); redacted logs; gitleaks in CI; no secrets in fixtures |
| Personal data exposure | Fixtures are synthetic; cached account data expires and is deleted by `clear_cache` / `revoke_authorization` |
| Unsafe input | Pydantic validation of every parameter; strict ID parsers; HTML-escaped approval page |
| Destructive API use | Provider interface has no update/delete methods; only `providers/live.py` imports the Google client |
| Quota exhaustion | Atomic per-bucket reservation before the first call; no retry on `quotaExceeded`; writes never auto-retried |

## 14. Test architecture
```mermaid
flowchart LR
    unit["unit<br/>ids, duration, similarity, quota, playlist logic, validation"] --> svc
    integ["integration<br/>services + FixtureProvider, quota + proposals"] --> svc
    sys["system<br/>in-process MCP Client: FR-1..FR-5, skill chain, prompt"] --> mcp
    neg["negative<br/>bad IDs, private/deleted, quotaExceeded, signup, expired token, rate limit"] --> mcp
    sec["security<br/>scopes, secrets, injection, approval bypass"] --> mcp
    live["live (scheduled)<br/>real API, fixed budget"] --> realapi
    mcp["MCPServer"] --> svc["services"]
    svc --> fx["FixtureProvider<br/>synthetic JSON"]
    realapi["LiveProvider"] --> yt[("YouTube API")]
```
CI (`.github/workflows/ci.yml`) runs lint, the offline suites on Ubuntu and Windows (Python 3.11/3.12) with an 85 %
coverage gate, gitleaks and the skill and brain validators, and keeps JUnit and coverage reports as artifacts.
`live-api.yml` runs the live suite weekly with a fixed quota budget (TQ-5). Plan and results:
`docs/tests/test-plan.md`, `docs/tests/test-results.md`; defects: `docs/tests/defect-log.md`.

## 15. Knowledge base and Agent Skills
```mermaid
flowchart LR
    ingest["brain-ingest (SK-3)"] -- "new research note" --> inbox["brain/inbox"]
    ingest --> res["brain/resources"]
    refine["brain-refine (SK-4)"] -- "PARA moves, merge duplicates, fix links" --> res
    refine --> archive["brain/archive"]
    query["brain-query (SK-5)"] -- "cited answers, ADR / SRS drafts" --> docs["docs/adr, SRS"]
    res --> query
    idx["brain/index.md + log.md"] --- res
    v2p["video-to-playlist (SK-1)"] -- "MCP prompt" --> server["MCP server"]
    lc["local-check (SK-2)"] -- "build, test, start, call, stop" --> server
```
The `brain/` folder is an Obsidian vault (PARA: projects, areas, resources, archive, inbox; `index.md` map of content,
`log.md` history). `scripts/validate_brain.py` and `scripts/validate_skills.py` enforce note and skill format in CI.

## 16. Concurrency and resilience
- Tool handlers run services in worker threads; each SQLite operation opens its own short connection.
- Proposal transitions use compare-and-set updates; `CREATING` holds a 2-minute lease so a crashed run can resume.
- Reads are retried at most 3 times with bounded exponential backoff on 429/5xx; writes and `quotaExceeded` never.

## 17. Architecture decisions
| ADR | Decision |
|---|---|
| [0001](adr/0001-runtime-and-sdk.md) | Python 3.11+, official MCP SDK (`MCPServer`), stdio only |
| [0002](adr/0002-confirmation-mechanism.md) | Elicitation, else local one-time code, else fail closed |
| [0003](adr/0003-quota-reservation.md) | Per-bucket ledger with atomic reservation before the first call |
| [0004](adr/0004-similarity-approach.md) | TF-IDF cosine plus weighted, explainable metadata signals |
| [0005](adr/0005-storage-and-token-storage.md) | One SQLite file outside the repo; tokens in the OS keychain |
