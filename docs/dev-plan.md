# Development plan (SE-4)

Work proceeds phase by phase. After each phase: lint + tests, then **stop for human review** before merging
(AI changes need human review, see `AGENTS.md`). Status reflects the state of the working tree on 2026-11-26.

| # | Phase / task | Main artifacts | Status |
|---|---|---|---|
| 1.1 | Repo, `pyproject.toml`, ruff, pytest, `.gitignore` | `pyproject.toml`, `.gitignore` | done, awaiting review |
| 1.2 | `AGENTS.md` (branches, PR + 1 review, AI review, no secrets, ai-session notes, how to test) | `AGENTS.md` | done, awaiting review |
| 1.3 | Obsidian vault with PARA, index, log | `brain/` | done, awaiting review |
| 1.4 | `brain-ingest` skill + 12 research notes | `skills/brain-ingest/`, `brain/resources/` | done; sources need human check |
| 1.5 | CI: install, lint, offline tests, gitleaks, validators | `.github/workflows/ci.yml` | written; first remote run pending |
| 1.6 | Validators + failing test cases | `scripts/validate_*.py`, `tests/unit/test_validators.py` | done |
| 2.1 | Provider interface (12 methods, no delete/update/history) | `providers/base.py` | done |
| 2.2 | Live provider: error mapping, read-only retries | `providers/live.py` | done (offline-tested with fake service) |
| 2.3 | Fixture provider: JSON, call log, error injection | `providers/fixture.py`, `tests/fixtures/` | done |
| 2.4 | ID parsing (all URL forms) | `ids.py` | done |
| 2.5 | ISO 8601 durations | `duration.py` | done |
| 2.6 | Quota buckets, atomic reserve, ledger, PT reset | `quota.py`, `config/quota.yaml` | done; `search.list` unit cost TBD |
| 2.7 | Cache 24 h / 7 d, `clear_cache` | `cache.py` | done |
| 2.8 | OAuth: loopback, state, PKCE, incremental write scope, revoke | `auth.py` | done; live sign-in demo pending |
| 2.9 | Redacting logs, per-tool timing | `logging_utils.py` | done |
| 3.1 | TF-IDF + weighted similarity | `similarity.py`, `config/similarity.yaml` | done; weights to tune (TBD-2) |
| 3.2 | FR-1 similar videos | `services/similar_videos.py` | done |
| 3.3 | FR-2 similar channels | `services/similar_channels.py` | done |
| 4.1 | FR-3 recommendations | `services/recommendations.py` | done |
| 4.2 | FR-4 engagement analysis | `services/engagement.py` | done |
| 5.1 | FR-5 propose (validation, filters, knapsack, persistence) | `services/playlist.py` | done |
| 5.2 | Approval: elicitation / local code / fail closed | `approval.py`, `server.py` | done |
| 5.3 | `create_playlist` state machine, atomic write quota, resume | `services/playlist.py` | done |
| 6.1 | MCP tools + resources, schemas, structured errors | `server.py`, `schemas.py` | done |
| 6.2 | Verify with demo client | user guide config snippet | **pending** (needs team OAuth client + Claude Desktop) |
| 7 | Agent Skills SK-1..SK-5 | `skills/` | done; evaluations pending (TQ-7) |
| 8 | Tests TQ-1..TQ-9, benchmark | `tests/`, `scripts/benchmark.py` | done; live run pending secrets |
| 9.1 | User guide, API reference, architecture, ADRs | `docs/` | done; full design (17 sections, 12 diagrams) in `docs/architecture.md` and `docs/design.pdf` (2026-11-27) |
| 9.2 | Traceability, stage reviews, ai-session note | `docs/traceability.md`, `brain/projects/` | done |
| 9.3 | CHANGELOG + tag `v1.0.0` | `CHANGELOG.md` | changelog done; **tag after review and green CI** |

## Remaining before release
1. Human review of all AI-generated changes (one PR per phase is recommended when importing this tree).
2. Push to GitHub, confirm CI green on the matrix, configure `live-api` environment secrets.
3. Live demo of FR-1..FR-5 and `video-to-playlist` in the chosen client; record results in
   `docs/tests/skill-evaluations.md`.
4. Set NFR-2 targets (TBD-3) from `scripts/benchmark.py` and live timings.
5. Fill Issue/PR columns in `docs/traceability.md`; tag `v1.0.0`.
