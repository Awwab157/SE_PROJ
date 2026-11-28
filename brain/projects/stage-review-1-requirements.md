---
title: Stage review 1 — requirements, brain, AGENTS.md, repository and CI skeleton
type: stage-review
status: pending-human-review
created: 2026-11-26
---
# Stage review 1 — requirements, brain, AGENTS.md, repository and CI skeleton

## Summary
Stage 1 deliverables:

| Deliverable | State | Where |
|---|---|---|
| SRS (FR, NFR, SK) | **open**: the team adds it to `docs/` | requirement IDs are used in `docs/traceability.md` |
| Obsidian vault with PARA, index, log | done | `brain/` ([[index]], log, `.obsidian/` config) |
| brain-ingest skill + at least 10 research notes | done, 12 notes with sources, requirement IDs and wikilinks | `skills/brain-ingest/`, `brain/resources/` |
| AGENTS.md | done | branches, PR + 1 review, AI rules, hard rules, commands, conventions |
| Repository and CI skeleton | done | `pyproject.toml`, `.gitignore`, `.gitleaks.toml`, PR template, `.github/workflows/ci.yml`, validators with failing-case tests |

Built in phase 1 of `BUILD_PLAN_PROMPT.md`; audited on 2026-11-27 (Obsidian config and PR template added).

## Decisions
- Runtime Python 3.11+ with the official MCP SDK; the installed SDK is v2, where FastMCP is called `MCPServer` (see [[mcp]]).
- Validators are plain scripts so they run in CI without the package installed.
- Obsidian settings are committed; workspace state (`workspace*.json`) is ignored.

## Open items
- SRS not yet in the repository: the team adds it to `docs/`; then fill the TBD rows in `docs/traceability.md` (NFR-3, 4, 6-9, 12, 14, 16, 18, SK-7, BR-3..7, SB-5/6).
- Human review of the research notes' sources (one fact — the 1,000-like limit — is taken from the SRS and still marked "to verify").
- Confirm the `search.list` unit cost for the team's Google Cloud project (see [[quota-management]]).
- The stray `SE_PROJ/` folder (an empty Obsidian vault) was committed in "Stage 1 finalized" and should be removed.

## Links
- [[yt-intel-mcp-release-1]] · [[obsidian-para-second-brain]] · [[agent-skills-format]] · [[stage-review-2-design]]
