---
title: YouTube API compliance
type: area
status: active
created: 2026-11-26
---
# YouTube API compliance

## Summary
Ongoing responsibility: stay within the YouTube API Services Terms and Developer Policies, the daily quota and the project's privacy rules.

- Official YouTube Data API v3 only; no scraping, no transcripts of others' videos, no watch history, no extra GCP projects.
- Only read the authorised user's own likes, subscriptions and playlists; never modify or delete existing content.
- Cached account data expires (24 h serve / 7 d purge) and is deleted by `clear_cache` and `revoke_authorization`.
- Review the quota page of the Google Cloud project each release and update `config/quota.yaml`.

## Links
- [[youtube-data-api-v3]] · [[quota-management]] · [[api-security-and-error-handling]]
