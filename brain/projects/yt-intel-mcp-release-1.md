---
title: YouTube Video Intelligence MCP — release 1.0
type: project
status: active
created: 2026-11-26
---
# YouTube Video Intelligence MCP — release 1.0

## Summary
Build an MCP server (stdio, Python, official MCP SDK) that finds similar videos and channels, recommends videos from the user's likes, subscriptions and playlists, analyses engagement, and creates playlists only after explicit user approval. Scope and decisions follow the SRS and `BUILD_PLAN_PROMPT.md`.

- Plan and task breakdown: `docs/dev-plan.md`
- Requirement → test → skill → note mapping: `docs/traceability.md`
- Definition of done: CI green, traceability complete, `local-check` passes on a team machine, live demo of FR-1..FR-5 and `video-to-playlist`.

## Links
- [[stage-review-1-skeleton]] · [[stage-review-2-implementation]] · [[stage-review-3-skills-and-docs]]
- [[youtube-data-api-v3]] · [[playlist-creation]] · [[quota-management]]
