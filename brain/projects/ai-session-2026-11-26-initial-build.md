---
title: AI session 2026-11-26 — initial build
type: ai-session
status: pending-human-review
created: 2026-11-26
---
# AI session 2026-11-26 — initial build

## Goal
Build release 1.0 from `BUILD_PLAN_PROMPT.md` (phases 1–9) in one session.

## What the AI did
- Generated the code, fixtures (synthetic only), tests, scripts, skills, research notes and docs.
- Ran lint, the offline test suite, the benchmark and `local-check` locally.
- Found and fixed: an unclosed SQLite connection that locked the state file on Windows; `mark_exhausted` leaving quota available after a reservation was released.
- No secrets, tokens or personal data were used; no network calls to YouTube were made.

## What worked and what failed
- Worked: phase-by-phase build with lint + tests after each phase; synthetic fixtures made the whole suite run offline.
- Worked: the benchmark and quota tests exposed two real defects early (D-001, D-002) and both got regression tests.
- Failed: the whole build happened in one session instead of stopping for review after each phase.
- Failed: the result was later committed straight to `main` without a pull request.

## Human review
- Required before merge (AGENTS.md): review every file, especially `services/playlist.py`, `approval.py`, `auth.py` and `quota.py`.
- Verify the research notes' sources and the two open TBDs in [[stage-review-1-requirements]].

## Links
- [[yt-intel-mcp-release-1]] · [[phase-review-implementation]]
