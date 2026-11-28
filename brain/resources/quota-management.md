---
title: Quota Management
type: research
status: distilled
created: 2026-11-26
tags: [quota, youtube, research]
---
# Quota Management

## Summary
Quota is a hard limit per bucket. Every workflow estimates and atomically reserves its cost **before** the first API call (FR-6).

## Key points
- Two buckets (configurable): `search_calls` (100/day, one per `search.list` page) and `units` (10,000/day).
- Costs: `playlists.insert` 50, `playlistItems.insert` 50, other list methods 1; `search.list` is charged in both buckets (conservative 100 units — TBD: confirm on the project's quota page).
- Reset at midnight America/Los_Angeles; the clock is injectable for tests (FR-6).
- Reservation uses SQLite `BEGIN IMMEDIATE` so two concurrent workflows cannot both take the last quota (TQ-9).
- Charges are recorded as consumed even if the request fails; unused reservation is released (FR-6).
- `quotaExceeded` from YouTube is never retried and marks the day as exhausted; 429/5xx reads are retried at most 3 times with bounded exponential backoff (FR-6.7, NFR-15).
- Cache: serve ≤24 h, refetch after, purge after 7 days; cache hits cost nothing (FR-6.6).

## Sources
- https://developers.google.com/youtube/v3/determine_quota_cost
- https://developers.google.com/youtube/v3/getting-started#quota
- https://developers.google.com/youtube/v3/docs/errors
- https://www.sqlite.org/lang_transaction.html

## Requirements
- FR-6, FR-6.1, FR-6.4, FR-6.6, FR-6.7, NFR-15, TQ-6, TQ-9

## Links
- [[youtube-data-api-v3]] · [[api-security-and-error-handling]] · [[playlist-creation]]
