---
title: Phase review 2–6 — core infrastructure and features
type: stage-review
status: pending-human-review
created: 2026-11-26
---
# Phase review 2–6 — core infrastructure and features

## Summary
Phases 2–6: provider interface (live + fixture), ID and duration parsing, quota ledger with atomic reservation, cache, OAuth with PKCE, redacting logs, similarity engine, FR-1..FR-5 services, approval mechanism and the MCP surface (9 tools, 3 resources).

## Decisions
- Quota is charged per HTTP request through a context-local reservation; a call outside a reservation is refused (see [[quota-management]]).
- Bounded reservations let read workflows run with less than the full plan and stop retrieval at the limit; writes are all-or-nothing.
- Channel ranking sorts by content similarity at the reported precision, so secondary signals only break ties (see [[tf-idf-and-cosine-similarity]]).
- Approval: elicitation first, else a local approval page with a hashed single-use code, else fail closed (see [[playlist-creation]]).

## What worked
- The provider interface let every service run against fixtures, so features were testable before any live credentials existed.
- Reserving quota before the first call made over-budget behaviour simple to test and explain.

## What did not work
- Two defects (an unclosed SQLite connection, quota re-opened after `quotaExceeded`) were only found by the benchmark and quota tests (D-001, D-002).
- The live provider could only be tested with a fake Google service until the first real sign-in.

## What to change
- Run the benchmark on Windows and Linux as part of each phase review.
- Get a real OAuth client early so live behaviour is checked during implementation, not after.

## Open items
- Live demo in the chosen MCP client with a real Google Cloud project (needs the team's OAuth client).
- Tune similarity weights on more fixtures (TBD-2) and set NFR-2 targets from `scripts/benchmark.py` (TBD-3).

## Links
- [[yt-intel-mcp-release-1]] · [[api-security-and-error-handling]] · [[oauth-2-0]]
