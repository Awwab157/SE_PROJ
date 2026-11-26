# ADR 0004 — Similarity: TF-IDF cosine plus weighted metadata signals

- Status: accepted (pending human review)
- Date: 2026-11-26
- Closes: TBD-2 (initial weights; tuning continues)

## Context
Similarity must be explainable, deterministic, cheap and based only on public metadata (no transcripts, no
embeddings service, no extra cloud project). Background:
[TF-IDF and Cosine Similarity](../../brain/resources/tf-idf-and-cosine-similarity.md),
[Channel Metadata](../../brain/resources/channel-metadata.md).

## Decision
- Documents: title (×2) + tags + description, URLs and stop words removed; `TfidfVectorizer` (sublinear TF) fitted on
  seed + candidates; cosine similarity.
- Video score = 0.55 text + 0.15 shared tags (Jaccard) + 0.10 category + 0.05 channel + 0.10 duration closeness +
  0.05 language; weights in `config/similarity.yaml`.
- Channels: profile from channel title/description and recent upload metadata only. Ranking sorts by content
  similarity (rounded to the reported precision); subscriber count, cadence and language only break exact ties, so they
  can never outrank higher content similarity.
- Stable sorts with ties broken by ID; explanations list shared terms/tags and matching signals.

## Consequences
- No semantic understanding beyond shared vocabulary; multilingual matches are weak.
- Weights are a starting point; tune on fixtures and record changes in the brain.
