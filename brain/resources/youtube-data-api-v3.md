---
title: YouTube Data API v3
type: research
status: distilled
created: 2026-11-26
tags: [youtube, api, research]
---
# YouTube Data API v3

## Summary
The official REST API for YouTube resources. It is the **only** data source this project may use: no scraping, no transcripts of other people's videos, no watch history (BR, hard rules).

## Key points
- Resources used: `videos`, `channels`, `search`, `playlists`, `playlistItems`, `subscriptions`, `videoCategories`.
- Every request costs quota, including invalid ones; the default project quota is 10,000 units/day, reset at midnight Pacific Time. See [[quota-management]].
- Typical costs: list methods 1 unit, `search.list` 100 units, `*.insert` 50 units (check the quota calculator; values live in `config/quota.yaml`).
- Reads of the user's own data need OAuth (see [[oauth-2-0]]); public metadata reads also go through OAuth here so there is a single authorisation path.
- The API exposes likes (`videos.list?myRating=like`), subscriptions and playlists, but **not** viewing history.
- Only `providers/live.py` may import `googleapiclient` (NFR-13), see [[api-security-and-error-handling]].

## Sources
- https://developers.google.com/youtube/v3/docs
- https://developers.google.com/youtube/v3/getting-started
- https://developers.google.com/youtube/v3/determine_quota_cost
- https://developers.google.com/youtube/terms/developer-policies

## Requirements
- FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, NFR-13, BR-1

## Links
- [[video-metadata]] · [[channel-metadata]] · [[playlist-creation]] · [[quota-management]] · [[oauth-2-0]]
