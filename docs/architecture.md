# Architecture (SE-2)

## Component diagram
```mermaid
flowchart LR
    client["MCP client (e.g. Claude Desktop)"] -- stdio JSON-RPC --> server["server.py\nMCPServer: 9 tools, 3 resources"]
    server --> schemas["schemas.py\ninput validation / output models"]
    server --> services
    server --> approval["approval.py\nelicitation / local code page"]
    subgraph services["services/"]
        sv[similar_videos] & sc[similar_channels] & rec[recommendations] & eng[engagement] & pl[playlist]
    end
    services --> sim["similarity.py\nTF-IDF + weighted score"]
    services --> quota["quota.py\nreserve / charge / release"]
    services --> cache["cache.py\nCachingProvider"]
    cache --> provider{{"providers/base.py\nYouTubeProvider"}}
    provider --> live["providers/live.py\n(only googleapiclient import)"]
    provider --> fixture["providers/fixture.py\n(tests, local-check)"]
    live --> yt[("YouTube Data API v3")]
    live --> auth["auth.py\nOAuth PKCE, keyring"]
    quota & cache & pl --> db[("state.db (SQLite)\n~/.yt-intel-mcp")]
    auth --> keychain[("OS keychain")]
    server --> logs["logging_utils.py\nredacted stderr logs"]
```

Small support modules not shown: `ids.py` (URL/ID parsing), `duration.py`, `errors.py`, `clock.py` (injectable
clock), `config.py` (YAML loading), `storage.py` (SQLite connections, state directory outside the repo).

## Sequence: playlist confirmation
```mermaid
sequenceDiagram
    actor U as User
    participant C as MCP client / model
    participant S as Server
    participant Q as Quota ledger
    participant Y as YouTube API
    C->>S: propose_playlist(topic, durations, language)
    S->>Q: reserve(search + videos.list)
    S->>Y: search.list, videos.list (reads)
    S-->>C: proposal (id, items, checks, est. quota) — no write
    C->>U: show proposal
    U->>C: "create it"
    C->>S: create_playlist(proposal_id)
    alt client supports elicitation
        S->>C: elicitation (exact proposal summary)
        C->>U: dialog
        U-->>C: accept / decline / cancel
        C-->>S: result
    else local approval
        S->>U: local page on 127.0.0.1 (summary + one-time code)
        S-->>C: approval_pending (no code)
        U->>C: types code
        C->>S: create_playlist(proposal_id, confirmation_code)
        S->>S: verify hash, single use
    else neither
        S-->>C: approval_unavailable (fail closed)
    end
    S->>S: incremental OAuth for write scope (first time)
    S->>Q: reserve 50 + 50×n units (atomic)
    S->>Y: playlists.insert
    S->>S: store playlist_id immediately
    loop each video
        S->>Y: playlistItems.insert (no auto-retry)
    end
    S-->>C: URL, completed/partial, privacy, quota used
```

## Proposal state machine
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

## Data model (state.db)
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
        text bucket PK "search_calls | units"
        int consumed
        int reserved
    }
    RESERVATIONS {
        text id PK
        text day
        text label
        text created_at
        text status "active | closed"
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

## Key properties
- **Quota before calls:** services build a plan, `quota.reserve()` runs in `BEGIN IMMEDIATE`, and providers call
  `quota.charge()` before every HTTP request; a charge without an active reservation is refused.
- **Isolation:** only `providers/live.py` imports `googleapiclient`; services see the `YouTubeProvider` interface, which
  has no update/delete methods.
- **Concurrency:** tool handlers run services in worker threads; each SQLite operation opens its own connection.
