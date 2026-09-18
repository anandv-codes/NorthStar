from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Sequence

from rank_bm25 import BM25Okapi

from ...ports import NoteRepository
from ..utils import combine_note_text, fingerprint_notes, tokenize
from .base import BaseRetrieval
from ....infrastructure.db.supabase_client import get_note_repository


@dataclass(slots=True)
class BM25Index:
    notes: list[dict[str, Any]]
    model: BM25Okapi | None

    @classmethod
    def from_notes(cls, notes: Sequence[dict[str, Any]]) -> "BM25Index":
        notes = list(notes)
        tokenized_corpus = [tokenize(combine_note_text(note)) for note in notes]
        model = BM25Okapi(tokenized_corpus) if tokenized_corpus else None
        return cls(notes=notes, model=model)

    def search(self, query: str, limit: int, k1: float, b: float) -> list[dict[str, Any]]:
        query_tokens = tokenize(query)
        if not query_tokens or not self.notes or self.model is None:
            return []

        # rank_bm25 defaults (k1=1.5, b=0.75) match the previous hand-rolled implementation.
        self.model.k1 = k1
        self.model.b = b
        scores = self.model.get_scores(query_tokens)

        scored_results = [
            (float(score), note)
            for score, note in zip(scores, self.notes)
            if score > 0.0
        ]
        scored_results.sort(
            key=lambda item: (
                -item[0],
                str(item[1].get("note_id") or ""),
            )
        )

        results: list[dict[str, Any]] = []
        for score, note in scored_results[:limit]:
            results.append(
                {
                    "note_id": note.get("note_id"),
                    "text": combine_note_text(note),
                    "summary": note.get("enriched_summary") or note.get("summary"),
                    "distance": score,
                }
            )
        return results


_INDEX_CACHE: dict[str, tuple[str, BM25Index]] = {}


def _get_index_for_user(user_id: str, note_repository: NoteRepository) -> BM25Index:
    notes = note_repository.query_notes_for_user(user_id=user_id)
    # Cheap identity check (note_id + updated_at only, no full-text hashing) to decide whether
    # the BM25 index needs rebuilding; still requires a full fetch since NoteRepository has no
    # lighter-weight "has anything changed" query today.
    cache_key = fingerprint_notes(notes)
    cached = _INDEX_CACHE.get(user_id)
    if cached and cached[0] == cache_key:
        return cached[1]

    index = BM25Index.from_notes(notes)
    _INDEX_CACHE[user_id] = (cache_key, index)
    return index


class SparseBM25Retriever(BaseRetrieval):
    def __init__(self, k1: float = 1.5, b: float = 0.75, note_repository: NoteRepository | None = None):
        self.k1 = k1
        self.b = b
        self._note_repository = note_repository

    def retrieve(self, query: str, user_id: str, limit: int = 5) -> List[dict[str, Any]]:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return []

        query_tokens = tokenize(normalized_query)
        if not query_tokens:
            return []

        note_repository = self._note_repository or get_note_repository()
        index = _get_index_for_user(user_id, note_repository)
        return index.search(normalized_query, limit=limit, k1=self.k1, b=self.b)
