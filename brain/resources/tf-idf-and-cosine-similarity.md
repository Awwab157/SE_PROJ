---
title: TF-IDF and Cosine Similarity
type: research
status: distilled
created: 2026-11-26
tags: [similarity, nlp, research]
---
# TF-IDF and Cosine Similarity

## Summary
Similarity is computed locally from metadata with TF-IDF vectors and cosine similarity, combined with a few weighted structured signals (FR-1.4, TBD-2).

## Key points
- TF-IDF weights a term by its frequency in a document and its rarity across the corpus; the vectoriser is fitted on seed + candidates so IDF reflects the candidate set.
- Cosine of L2-normalised vectors = dot product; range 0..1 for non-negative TF-IDF.
- Document = title (twice) + tags + description (URLs removed, English + domain stop words).
- Video score = 0.55 text cosine + 0.15 shared tags (Jaccard) + 0.10 same category + 0.05 same channel + 0.10 duration closeness + 0.05 language match (weights in `config/similarity.yaml`).
- Deterministic: stable sort, ties broken by ID; scores rounded.
- Channels: content similarity is primary; secondary signals only order channels whose content similarity is equal at the reported precision (FR-2).
- Explanations list shared terms/tags and matching signals so results are explainable.

## Sources
- https://scikit-learn.org/stable/modules/feature_extraction.html#tfidf-term-weighting
- https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html
- https://nlp.stanford.edu/IR-book/html/htmledition/tf-idf-weighting-1.html

## Requirements
- FR-1, FR-1.4, FR-2, FR-3, TBD-2

## Links
- [[video-metadata]] · [[channel-metadata]]
