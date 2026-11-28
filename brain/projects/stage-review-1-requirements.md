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

## What worked
- Starting from a written build plan with requirement IDs made the vault, AGENTS.md and CI skeleton consistent from day one.
- The `brain-ingest` template (sources, requirement IDs, wikilinks) produced 12 research notes that later ADRs and skills could cite (SB-3).
- Validators as plain scripts with failing-case tests caught broken links and missing sections immediately.

## What did not work
- The SRS itself never landed in the repository, so many requirement IDs (NFR-3, 4, 6–9 …) have no text to trace.
- Work was committed directly to `main` without issues or pull requests, against AGENTS.md (SB-5, SE-5).
- Obsidian was first opened with "Create new vault", which committed a stray empty vault (`SE_PROJ/`).

## What to change
- Put the SRS in `docs/` before any further requirement work and fill the traceability TBDs from it.
- Open a GitHub issue first, work on a branch, merge through a reviewed PR.
- Open the vault with "Open folder as vault" on `brain/` only.

## Open items
- SRS not yet in the repository: the team adds it to `docs/`; then fill the TBD rows in `docs/traceability.md` (NFR-3, 4, 6-9, 12, 14, 16, 18, SK-7, BR-3..7, SB-5/6).
- Human review of the research notes' sources (one fact — the 1,000-like limit — is taken from the SRS and still marked "to verify").
- Confirm the `search.list` unit cost for the team's Google Cloud project (see [[quota-management]]).
- ~~Remove the stray `SE_PROJ/` folder~~ removed on 2026-11-28 (branch `ai/sdlc-gaps`).

## Links
- [[yt-intel-mcp-release-1]] · [[obsidian-para-second-brain]] · [[agent-skills-format]] · [[stage-review-2-design]]
