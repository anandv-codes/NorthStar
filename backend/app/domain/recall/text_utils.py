"""Small text helpers shared by candidate scoring and card validation."""
from __future__ import annotations

import hashlib
import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for",
    "from", "has", "have", "how", "i", "in", "is", "it", "its", "of", "on",
    "or", "that", "the", "their", "then", "there", "these", "they", "this",
    "to", "was", "were", "what", "when", "where", "which", "who", "why",
    "will", "with", "you", "your",
}


def normalize_text(text: str) -> str:
    """Lowercase, collapse whitespace, strip surrounding punctuation."""
    normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
    return normalized.strip(" \t\r\n.,;:!?\"'")


def dedupe_key(item_type: str, text: str) -> str:
    """Stable key for de-duplicating candidates/cards across notes."""
    digest = hashlib.sha1(normalize_text(text).encode("utf-8")).hexdigest()
    return f"{item_type}:{digest}"


def content_tokens(text: str, drop_stop_words: bool = True) -> set[str]:
    tokens = set(_TOKEN_RE.findall(str(text or "").lower()))
    if drop_stop_words:
        tokens -= _STOP_WORDS
    return tokens


def jaccard_similarity(left: str, right: str) -> float:
    left_tokens = content_tokens(left)
    right_tokens = content_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    union = left_tokens | right_tokens
    if not union:
        return 0.0
    return len(left_tokens & right_tokens) / len(union)


def token_overlap_ratio(answer: str, context: str) -> float:
    """Fraction of answer tokens that also appear in the supplied context."""
    answer_tokens = content_tokens(answer)
    if not answer_tokens:
        return 0.0
    context_tokens = content_tokens(context)
    return len(answer_tokens & context_tokens) / len(answer_tokens)
