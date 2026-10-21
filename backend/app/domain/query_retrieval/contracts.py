"""Shared contracts for retrieval and context assembly.

The retrieval engine is intentionally policy-free: callers describe what they
need with a ``RetrievalRequest`` and receive a ``RetrievalResult``. Task-specific
policies (chat rewrite, ingestion entity lookup, recall context reuse) live in
their respective services.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

RetrievalMode = Literal[
    "chat",
    "note_ingestion",
    "recall_question",
    "recall_answer",
    "summary",
]

MAX_RETRIEVAL_LIMIT = 20
DEFAULT_CANDIDATE_MULTIPLIER = 3.0


def _clamp_limit(value: int) -> int:
    return max(1, min(int(value), MAX_RETRIEVAL_LIMIT))


@dataclass(frozen=True, slots=True)
class RetrievalRequest:
    """A user-scoped retrieval request independent of any task policy."""

    user_id: str
    query: str
    limit: int = 5
    mode: RetrievalMode = "chat"
    alternate_query: str | None = None
    exclude_note_id: str | None = None
    candidate_limit: int | None = None
    include_exact_identifiers: bool = True
    rerank: bool = True

    @property
    def clamped_limit(self) -> int:
        return _clamp_limit(self.limit)

    def candidate_depth(self, multiplier: float = DEFAULT_CANDIDATE_MULTIPLIER) -> int:
        """Per-source candidate depth before fusion/reranking."""
        if self.candidate_limit is not None:
            return _clamp_limit(self.candidate_limit)
        expanded = int(round(self.clamped_limit * max(1.0, multiplier)))
        return _clamp_limit(max(self.clamped_limit, expanded))


@dataclass(slots=True)
class RetrievalResult:
    """Retrieved notes plus enough metadata to explain the ranking."""

    request: RetrievalRequest
    candidates: list[dict[str, Any]] = field(default_factory=list)
    source_counts: dict[str, int] = field(default_factory=dict)
    exact_identifiers: list[str] = field(default_factory=list)

    @property
    def note_ids(self) -> list[str]:
        return [
            str(candidate.get("note_id"))
            for candidate in self.candidates
            if candidate.get("note_id")
        ]


@dataclass(slots=True)
class ContextBundle:
    """Normalized context passed to downstream LLM tasks."""

    notes: list[dict[str, Any]] = field(default_factory=list)
    entity_names: list[str] = field(default_factory=list)
    memory_items: list[dict[str, Any]] = field(default_factory=list)
    sources: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "related_notes": self.notes,
            "matched_entity_names": self.entity_names,
            "memory_items": self.memory_items,
            "retrieval_sources": self.sources,
        }
