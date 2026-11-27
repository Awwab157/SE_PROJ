# YouTube Video Intelligence MCP Server

An [MCP](https://modelcontextprotocol.io) server (stdio, Python) that gives an AI client grounded YouTube
abilities through the official **YouTube Data API v3**:

| Tool | What it does | Writes to YouTube |
|---|---|---|
| `find_similar_videos` | Similar public videos for a seed video, with scores and explanations | no |
| `find_similar_channels` | Similar channels ranked by content similarity | no |
| `recommend_videos` | Recommendations from your likes, subscriptions and playlists | no |
| `analyze_engagement` | Top channels/categories, subscriptions, trends, duration buckets, period comparison | no |
| `propose_playlist` | Plans a playlist for a topic and duration budget (no write) | no |
| `create_playlist` | Creates the proposed playlist **after you approve it** | **yes** |
| `start_authorization` / `revoke_authorization` | Connect / disconnect your YouTube account | no |
| `clear_cache` | Delete cached YouTube data | no |

Read-only resources: `quota://status`, `config://server`, `proposal://{id}`.

## Safety by design
- Read features use only the `youtube.readonly` scope; the write scope is requested only when a playlist is created.
- Playlists are created only after **you** approve the exact proposal, through your client's confirmation dialog or a
  local approval page with a one-time code. Playlists are private by default; nothing is ever modified or deleted.
- Quota is reserved before the first API call; over-budget requests are rejected up front.
- Tokens live in the OS keychain; logs are redacted; YouTube text is treated as untrusted data.

## Quick start
```bash
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python scripts/local_check.py                    # offline end-to-end check with fixture data
```
Try it without any AI app: `python scripts/yt.py --sample similar pdIntro0001` (sample data) or, after the one-time
Google setup, `python scripts/yt.py similar <video URL>` on real YouTube data.
Connecting a real account and an MCP client: see [docs/user-guide.md](docs/user-guide.md).

## Documentation
- [New computer setup](docs/new-machine-setup.md) · [User guide](docs/user-guide.md) · [API reference](docs/api.md) · [Architecture](docs/architecture.md)
- [ADRs](docs/adr/) · [Development plan](docs/dev-plan.md) · [Traceability](docs/traceability.md)
- Contributor and AI-agent rules: [AGENTS.md](AGENTS.md) · Agent Skills: [skills/](skills/) · Team notes: [brain/index.md](brain/index.md)

## Repository layout
```
src/yt_intel_mcp/   server, schemas, providers (live/fixture), services, quota, cache, auth, approval
config/             quota.yaml (cost table), similarity.yaml (weights, limits)
tests/              unit, integration, system, negative, security (offline) and live (scheduled)
skills/             video-to-playlist, local-check, brain-ingest, brain-refine, brain-query
brain/              Obsidian PARA vault (research notes, stage reviews)
docs/               user guide, API, architecture, ADRs, plan, traceability, test records
scripts/            validators, benchmark, local check, API doc generator
```
