"""Deterministic text chunking for embedding-based retrieval.

Long notes are split into overlapping sentence-packed chunks so a single
embedding does not have to represent an entire document. Pure functions only,
so chunking behavior is unit-testable without an embedding provider or DB.

Targets:
- prefer whole sentences/paragraphs;
- keep each chunk at or below ``max_chars`` (soft cap: a single sentence longer
  than the cap is hard-split, and overlap can push the effective size up);
- carry ``overlap_chars`` of trailing context into the next chunk so a fact
  spanning a boundary is still fully present in at least one chunk.
"""
from __future__ import annotations

import re

DEFAULT_MAX_CHARS = 800
DEFAULT_OVERLAP_CHARS = 100

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def chunk_text(
    text: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[str]:
    """Split ``text`` into overlapping chunks. Returns ``[]`` for blank input."""
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be >= 0 and < max_chars")

    normalized = (text or "").strip()
    if not normalized:
        return []

    sentences: list[str] = []
    for paragraph in _PARAGRAPH_SPLIT.split(normalized):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        for sentence in _SENTENCE_SPLIT.split(paragraph):
            sentence = sentence.strip()
            if sentence:
                sentences.extend(_hard_split(sentence, max_chars))

    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if current and len(candidate) > max_chars:
            chunks.append(current)
            tail = current[-overlap_chars:] if overlap_chars else ""
            current = f"{tail} {sentence}".strip() if tail else sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _hard_split(sentence: str, max_chars: int) -> list[str]:
    if len(sentence) <= max_chars:
        return [sentence]
    return [sentence[i : i + max_chars] for i in range(0, len(sentence), max_chars)]
