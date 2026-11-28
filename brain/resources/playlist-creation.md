---
title: Playlist Creation
type: research
status: distilled
created: 2026-11-26
tags: [youtube, playlists, safety, research]
---
# Playlist Creation

## Summary
The only write path. A two-step propose → user-approved create flow with an atomic quota reservation and an idempotent state machine (FR-5).

## Key points
- `playlists.insert` (snippet.title, snippet.description, status.privacyStatus) and `playlistItems.insert` (snippet.playlistId, snippet.resourceId.videoId): 50 units each.
- `youtubeSignupRequired`: the Google account has no YouTube channel → tell the user to create one.
- Inserts are not idempotent → store the new playlist ID **immediately** and resume item insertion on retry; never auto-retry writes (FR-5.9).
- State machine: `PROPOSED → APPROVED → CREATING → COMPLETED | PARTIAL`; `DECLINED`, `EXPIRED` terminal; proposals expire after 10 minutes.
- Approval (TBD-5): MCP elicitation if supported; otherwise a single-use code shown only on a local approval page; otherwise fail closed. The code is stored hashed and never appears in tool results, resources, logs or errors (FR-5.6).
- Playlists are private by default (BR-2); existing videos/playlists are never modified or deleted.
- Selection: fill the requested duration without exceeding it, ≥90 % when achievable (greedy + bounded subset-sum), report shortfall and unmet constraints otherwise.

## Sources
- https://developers.google.com/youtube/v3/docs/playlists/insert
- https://developers.google.com/youtube/v3/docs/playlistItems/insert
- https://developers.google.com/youtube/v3/docs/errors

## Requirements
- FR-5.1, FR-5.2, FR-5.5, FR-5.6, FR-5.8, FR-5.9, FR-5.10, BR-2, UI-2, UI-5

## Links
- [[quota-management]] · [[oauth-2-0]] · [[mcp]] · [[api-security-and-error-handling]]
