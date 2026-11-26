---
title: Channel Metadata
type: research
status: distilled
created: 2026-11-26
tags: [youtube, metadata, channels, research]
---
# Channel Metadata

## Summary
How channel references are resolved and which channel fields may be used for similarity (FR-2).

## Key points
- `channels.list` resolves `id=UC…`, `forHandle=@handle` and `forUsername=` (legacy `/user/` URLs).
- Legacy `/c/` custom URLs have **no** lookup parameter: use channel-only `search.list`; if more than one channel matches, return the candidates and never auto-pick (FR-2.2).
- `statistics.hiddenSubscriberCount = true` → do not show a subscriber count (FR-2). Public counts are rounded by YouTube.
- `contentDetails.relatedPlaylists.uploads` gives the uploads playlist → recent upload titles/descriptions build the channel profile.
- The profile uses only channel title/description and recent upload metadata — no `topicIds`, no assumed keywords (FR-2).
- Subscriber count, upload cadence and language are secondary signals that cannot outrank higher content similarity (FR-2), see [[tf-idf-and-cosine-similarity]].

## Sources
- https://developers.google.com/youtube/v3/docs/channels
- https://developers.google.com/youtube/v3/docs/channels/list
- https://developers.google.com/youtube/v3/docs/search/list

## Requirements
- FR-2, FR-2.1, FR-2.2

## Links
- [[youtube-data-api-v3]] · [[video-metadata]] · [[tf-idf-and-cosine-similarity]]
