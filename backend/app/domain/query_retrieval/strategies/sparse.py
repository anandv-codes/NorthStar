from __future__ import annotations

import os
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Sequence

from rank_bm25 import BM25Okapi

from ...ports import NoteRepository
from ..utils import combine_note_text, contains_identifier, extract_identifiers, fingerprint_notes, tokenize
from .base import BaseRetrieval


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

    def search(
        self,
        query: str,
        limit: int,
        k1: float,
        b: float,
        exclude_note_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query_tokens = tokenize(query)
        if not query_tokens or not self.notes or self.model is None:
            return []

        # rank_bm25 defaults (k1=1.5, b=0.75) match the previous hand-rolled implementation.
        self.model.k1 = k1
        self.model.b = b
        scores = self.model.get_scores(query_tokens)

        excluded = str(exclude_note_id) if exclude_note_id else None
        scored_results = [
            (float(score), note)
            for score, note in zip(scores, self.notes)
            if score > 0.0 and str(note.get("note_id") or "") != excluded
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

    def search_identifiers(
        self,
        identifiers: Sequence[str],
        limit: int,
        exclude_note_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Find notes containing explicit identifiers such as ``ITEM-4101``."""
        normalized_identifiers = [str(item).lower() for item in identifiers if item]
        if not normalized_identifiers or not self.notes:
            return []

        excluded = str(exclude_note_id) if exclude_note_id else None
        matches: list[tuple[int, dict[str, Any]]] = []
        for note in self.notes:
            if str(note.get("note_id") or "") == excluded:
                continue
            note_text = combine_note_text(note)
            hit_count = sum(
                1 for identifier in normalized_identifiers if contains_identifier(note_text, identifier)
            )
            if hit_count:
                matches.append((hit_count, note))

        matches.sort(
            key=lambda item: (
                -item[0],
                str(item[1].get("note_id") or ""),
            )
        )

        results: list[dict[str, Any]] = []
        for hit_count, note in matches[:limit]:
            results.append(
                {
                    "note_id": note.get("note_id"),
                    "text": combine_note_text(note),
                    "summary": note.get("enriched_summary") or note.get("summary"),
                    "distance": 0.0,
                    "exact_match_count": hit_count,
                }
            )
        return results


_INDEX_CACHE: OrderedDict[str, tuple[str, BM25Index]] = OrderedDict()
_INDEX_CACHE_LOCK = threading.Lock()
_INDEX_CACHE_MAX_USERS = max(1, int(os.getenv("BM25_INDEX_CACHE_MAX_USERS", "128")))


def _get_index_for_user(user_id: str, note_repository: NoteRepository) -> BM25Index:
    notes = note_repository.query_notes_for_user(user_id=user_id)
    # Cheap identity check (note_id + updated_at only, no full-text hashing) to decide whether
    # the BM25 index needs rebuilding; still requires a full fetch since NoteRepository has no
    # lighter-weight "has anything changed" query today.
    cache_key = fingerprint_notes(notes)

    with _INDEX_CACHE_LOCK:
        cached = _INDEX_CACHE.get(user_id)
        if cached and cached[0] == cache_key:
            _INDEX_CACHE.move_to_end(user_id)
            return cached[1]

        index = BM25Index.from_notes(notes)
        _INDEX_CACHE[user_id] = (cache_key, index)
        _INDEX_CACHE.move_to_end(user_id)
        while len(_INDEX_CACHE) > _INDEX_CACHE_MAX_USERS:
            _INDEX_CACHE.popitem(last=False)
        return index


def clear_index_cache() -> None:
    """Clear the process-wide BM25 cache (used by tests and re-index hooks)."""
    with _INDEX_CACHE_LOCK:
        _INDEX_CACHE.clear()


class SparseBM25Retriever(BaseRetrieval):
    def __init__(self, k1: float = 1.5, b: float = 0.75, note_repository: NoteRepository | None = None):
        self.k1 = k1
        self.b = b
        self._note_repository = note_repository

    def _repository(self) -> NoteRepository:
        if self._note_repository is not None:
            return self._note_repository
        from ....infrastructure.db.supabase_client import get_note_repository

        return get_note_repository()

    def retrieve(
        self,
        query: str,
        user_id: str,
        limit: int = 5,
        exclude_note_id: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return []

        query_tokens = tokenize(normalized_query)
        if not query_tokens:
            return []

        index = _get_index_for_user(user_id, self._repository())
        return index.search(
            normalized_query,
            limit=limit,
            k1=self.k1,
            b=self.b,
            exclude_note_id=exclude_note_id,
        )

    def retrieve_exact_identifiers(
        self,
        query: str,
        user_id: str,
        limit: int = 5,
        exclude_note_id: str | None = None,
    ) -> list[dict[str, Any]]:
        identifiers = extract_identifiers(query)
        if not identifiers:
            return []
        index = _get_index_for_user(user_id, self._repository())
        return index.search_identifiers(
            identifiers,
            limit=limit,
            exclude_note_id=exclude_note_id,
        )
