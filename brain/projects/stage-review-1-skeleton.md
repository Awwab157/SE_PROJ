---
title: Stage review 1 — skeleton, CI and process
type: stage-review
status: pending-human-review
created: 2026-11-26
---
# Stage review 1 — skeleton, CI and process

## Summary
Phase 1 deliverables exist: `pyproject.toml` (ruff, pytest), `.gitignore` for secrets and state, `AGENTS.md`, the PARA vault with [[index]] and log, the `brain-ingest` skill and 12 research notes, `ci.yml` (lint, offline tests, gitleaks, skill and brain validators) and validators with failing-case tests.

## Decisions
- Runtime Python 3.11+ with the official MCP SDK; the installed SDK is v2, where FastMCP is called `MCPServer` (see [[mcp]]).
- Validators are plain scripts so they run in CI without the package installed.

## Open items
- Human review of the research notes' sources (one fact — the 1,000-like limit — is taken from the SRS and still marked "to verify").
- Confirm the `search.list` unit cost for the team's Google Cloud project (see [[quota-management]]).

## Links
- [[yt-intel-mcp-release-1]] · [[obsidian-para-second-brain]] · [[agent-skills-format]]
