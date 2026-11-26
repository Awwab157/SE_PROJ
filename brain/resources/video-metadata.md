---
title: Video Metadata
type: research
status: distilled
created: 2026-11-26
tags: [youtube, metadata, research]
---
# Video Metadata

## Summary
What `videos.list` returns and how missing or odd values are handled. Missing metadata never crashes and is never fabricated (hard rule).

## Key points
- `snippet`: title, description, tags (optional, often missing), categoryId, channelId, channelTitle, publishedAt, defaultLanguage, defaultAudioLanguage, liveBroadcastContent.
- `contentDetails.duration` is ISO 8601 (`PT1H2M10S` = 3730 s). Live streams report `P0D`; we treat it, zero and missing as **unknown** (`None`), never 0 (FR-4.5).
- `status.privacyStatus` / `status.uploadStatus`: private or not `processed` means unavailable; deleted or private IDs are simply absent from the response (FR-1).
- Language = `defaultAudioLanguage`, else `defaultLanguage`, reduced to the ISO 639-1 primary subtag. Unknown language is excluded **and counted** in playlist proposals (FR-5.4).
- Missing seed fields are reported in `unavailable_fields` (FR-1.2); no tags → title/description only; no usable text → `insufficient_metadata` (FR-1.6).
- All text fields are **untrusted data** (prompt injection risk), see [[api-security-and-error-handling]].
- Likes have no "liked at" timestamp; like trends use the video publish date (FR-4). The SRS states a 1,000-item limit for liked videos (to verify against current docs).

## Sources
- https://developers.google.com/youtube/v3/docs/videos
- https://developers.google.com/youtube/v3/docs/videos/list
- https://en.wikipedia.org/wiki/ISO_8601#Durations

## Requirements
- FR-1, FR-1.2, FR-1.6, FR-3, FR-4.5, FR-5.3, FR-5.4

## Links
- [[youtube-data-api-v3]] · [[tf-idf-and-cosine-similarity]] · [[playlist-creation]]
