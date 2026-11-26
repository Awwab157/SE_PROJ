"""TF-IDF + weighted similarity scoring (FR-1, FR-2). Deterministic: stable sorts, ties broken by ID."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

from yt_intel_mcp.schemas import VideoMeta

DOMAIN_STOP_WORDS = {
    "video",
    "videos",
    "subscribe",
    "channel",
    "http",
    "https",
    "www",
    "com",
    "like",
    "watch",
    "official",
    "episode",
    "new",
    "full",
    "youtube",
    "link",
    "links",
    "follow",
    "instagram",
    "twitter",
    "tiktok",
    "facebook",
    "patreon",
    "today",
    "part",
}
STOP_WORDS = frozenset(ENGLISH_STOP_WORDS) | DOMAIN_STOP_WORDS
TOKEN_PATTERN = r"(?u)\b[^\W\d_]{2,}\b"
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_TOKEN_RE = re.compile(TOKEN_PATTERN)
MAX_DESCRIPTION_CHARS = 2000


def clean_text(text: str | None) -> str:
    return _URL_RE.sub(" ", text or "")


def tokens(text: str | None) -> list[str]:
    return [t for t in _TOKEN_RE.findall(clean_text(text).lower()) if t not in STOP_WORDS]


def video_document(video: VideoMeta) -> str:
    title = video.title or ""
    tags = " ".join(video.tags)
    description = (video.description or "")[:MAX_DESCRIPTION_CHARS]
    # Title counted twice: it is the most reliable field.
    return clean_text(f"{title} {title} {tags} {description}")


def has_text(doc: str) -> bool:
    return bool(tokens(doc))


def keyword_terms(title: str | None, tags: Sequence[str], description: str | None, k: int) -> list[str]:
    """Top terms from one item's metadata (title x3, tags x2, description x1)."""
    weights: Counter[str] = Counter()
    for term in tokens(title):
        weights[term] += 3
    for term in tokens(" ".join(tags)):
        weights[term] += 2
    for term in tokens((description or "")[:MAX_DESCRIPTION_CHARS]):
        weights[term] += 1
    return [t for t, _ in sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))[:k]]


def tfidf_cosines(seed_doc: str, docs: Sequence[str]) -> tuple[list[float], list[list[str]]]:
    """Cosine of each doc to the seed (vectoriser fitted on seed + docs) and top shared terms."""
    if not docs:
        return [], []
    vectorizer = TfidfVectorizer(
        stop_words=sorted(STOP_WORDS), token_pattern=TOKEN_PATTERN, sublinear_tf=True, lowercase=True
    )
    try:
        matrix = vectorizer.fit_transform([seed_doc, *docs])
    except ValueError:  # empty vocabulary
        return [0.0] * len(docs), [[] for _ in docs]
    vocab = vectorizer.get_feature_names_out()
    seed_vec = matrix[0]
    sims = (matrix[1:] @ seed_vec.T).toarray().ravel()
    shared: list[list[str]] = []
    seed_weights = dict(zip(seed_vec.indices, seed_vec.data, strict=False))
    for i in range(1, matrix.shape[0]):
        row = matrix[i]
        overlap = [
            (seed_weights[j] * w, vocab[j]) for j, w in zip(row.indices, row.data, strict=False) if j in seed_weights
        ]
        overlap.sort(key=lambda x: (-x[0], x[1]))
        shared.append([term for _, term in overlap[:3]])
    return [round(float(s), 6) for s in sims], shared


@dataclass
class ScoredVideo:
    video: VideoMeta
    score: float
    components: dict[str, float]
    explanation: str


def _duration_closeness(a: int | None, b: int | None) -> float | None:
    if not a or not b:
        return None
    return 1.0 - abs(a - b) / max(a, b)


def _minutes(seconds: int) -> str:
    return f"{round(seconds / 60)} min"


def score_videos(seed: VideoMeta, candidates: Sequence[VideoMeta], weights: Mapping[str, float]) -> list[ScoredVideo]:
    cosines, shared_terms = tfidf_cosines(video_document(seed), [video_document(c) for c in candidates])
    seed_tags = {t.lower() for t in seed.tags}
    scored: list[ScoredVideo] = []
    for cand, cos, terms in zip(candidates, cosines, shared_terms, strict=True):
        cand_tags = {t.lower() for t in cand.tags}
        shared_tags = sorted(seed_tags & cand_tags)
        tag_score = len(shared_tags) / len(seed_tags | cand_tags) if seed_tags and cand_tags else 0.0
        same_category = 1.0 if seed.category_id and seed.category_id == cand.category_id else 0.0
        same_channel = 1.0 if seed.channel_id and seed.channel_id == cand.channel_id else 0.0
        closeness = _duration_closeness(seed.duration_seconds, cand.duration_seconds)
        language = 1.0 if seed.language and seed.language == cand.language else 0.0
        components = {
            "text_cosine": round(cos, 4),
            "shared_tags": round(tag_score, 4),
            "same_category": same_category,
            "same_channel": same_channel,
            "duration_closeness": round(closeness or 0.0, 4),
            "language_match": language,
        }
        score = round(sum(weights.get(k, 0.0) * v for k, v in components.items()), 4)
        parts = [f"text similarity {components['text_cosine']:.2f}"]
        if terms:
            parts.append("shared terms: " + ", ".join(terms))
        if shared_tags:
            parts.append("shared tags: " + ", ".join(shared_tags[:5]))
        if same_category:
            parts.append("same category")
        if same_channel:
            parts.append("same channel")
        if closeness is not None and closeness >= 0.5:
            parts.append(f"similar duration ({_minutes(cand.duration_seconds)} vs {_minutes(seed.duration_seconds)})")
        if language:
            parts.append(f"same language ({cand.language})")
        scored.append(ScoredVideo(cand, score, components, "; ".join(parts)))
    scored.sort(key=lambda s: (-s.score, s.video.video_id))
    return scored


# --- channels -----------------------------------------------------------------------------------


@dataclass
class ChannelProfile:
    channel_id: str
    title: str | None
    document: str
    subscriber_count: int | None = None
    uploads_per_30d: float | None = None
    language: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class ScoredChannel:
    profile: ChannelProfile
    score: float
    secondary_score: float
    explanation: str


def _ratio_closeness(a: float | None, b: float | None, log: bool = False) -> float:
    if a is None or b is None or a <= 0 or b <= 0:
        return 0.0
    if log:
        a, b = math.log10(a + 1), math.log10(b + 1)
    return min(a, b) / max(a, b)


def rank_channels(
    seed: ChannelProfile,
    candidates: Sequence[ChannelProfile],
    secondary_weights: Mapping[str, float],
    precision: int = 3,
) -> list[ScoredChannel]:
    """Rank by content similarity; secondary signals only order channels whose content similarity is
    equal at the reported precision, so they can never outrank higher content similarity (FR-2)."""
    cosines, shared_terms = tfidf_cosines(seed.document, [c.document for c in candidates])
    results: list[ScoredChannel] = []
    for cand, cos, terms in zip(candidates, cosines, shared_terms, strict=True):
        content = round(cos, precision)
        subs = _ratio_closeness(seed.subscriber_count, cand.subscriber_count, log=True)
        cadence = _ratio_closeness(seed.uploads_per_30d, cand.uploads_per_30d)
        language = 1.0 if seed.language and seed.language == cand.language else 0.0
        secondary = round(
            secondary_weights.get("subscriber_closeness", 0) * subs
            + secondary_weights.get("upload_cadence", 0) * cadence
            + secondary_weights.get("language_match", 0) * language,
            4,
        )
        parts = [f"content similarity {content:.{precision}f}"]
        if terms:
            parts.append("shared topics: " + ", ".join(terms))
        if language:
            parts.append(f"same language ({cand.language})")
        results.append(ScoredChannel(cand, content, secondary, "; ".join(parts)))
    results.sort(key=lambda r: (-r.score, -r.secondary_score, r.profile.channel_id))
    return results
