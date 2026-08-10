from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, List, Sequence

from ..utils import combine_note_text, fingerprint_notes, tokenize
from .base import BaseRetrieval


@dataclass(slots=True)
class IndexedDocument:
    note: dict[str, Any]
    term_frequencies: Counter[str]
    length: int


@dataclass(slots=True)
class BM25Index:
    documents: list[IndexedDocument]
    document_frequency: dict[str, int]
    average_document_length: float

    @classmethod
    def from_notes(cls, notes: Sequence[dict[str, Any]]) -> "BM25Index":
        documents: list[IndexedDocument] = []
        document_frequency: dict[str, int] = {}
        total_length = 0

        for note in notes:
            tokens = tokenize(combine_note_text(note))
            term_frequencies = Counter(tokens)
            documents.append(
                IndexedDocument(
                    note=note,
                    term_frequencies=term_frequencies,
                    length=len(tokens),
                )
            )
            total_length += len(tokens)
            for token in term_frequencies:
                document_frequency[token] = document_frequency.get(token, 0) + 1

        average_document_length = total_length / len(documents) if documents else 0.0
        return cls(
            documents=documents,
            document_frequency=document_frequency,
            average_document_length=average_document_length,
        )

    def search(self, query: str, limit: int, k1: float, b: float) -> list[dict[str, Any]]:
        query_tokens = tokenize(query)
        if not query_tokens or not self.documents:
            return []

        document_count = len(self.documents)
        scored_results: list[tuple[float, dict[str, Any]]] = []

        for document in self.documents:
            if document.length <= 0:
                continue

            score = 0.0
            for token in query_tokens:
                term_frequency = document.term_frequencies.get(token)
                if not term_frequency:
                    continue

                document_frequency = self.document_frequency.get(token, 0)
                idf = math.log((document_count - document_frequency + 0.5) / (document_frequency + 0.5) + 1.0)
                denominator = term_frequency + k1 * (
                    1.0 - b + b * (document.length / self.average_document_length if self.average_document_length > 0 else 1.0)
                )
                score += idf * ((term_frequency * (k1 + 1.0)) / denominator)

            if score > 0.0:
                scored_results.append((score, document.note))

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


def _get_index_for_user(user_id: str) -> BM25Index:
    from ....infrastructure.db.supabase_client import query_notes_for_user

    notes = query_notes_for_user(user_id=user_id)
    cache_key = fingerprint_notes(notes)
    cached = _INDEX_CACHE.get(user_id)
    if cached and cached[0] == cache_key:
        return cached[1]

    index = BM25Index.from_notes(notes)
    _INDEX_CACHE[user_id] = (cache_key, index)
    return index


class SparseBM25Retriever(BaseRetrieval):
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    def retrieve(self, query: str, user_id: str, limit: int = 5) -> List[dict[str, Any]]:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return []

        query_tokens = tokenize(normalized_query)
        if not query_tokens:
            return []

        index = _get_index_for_user(user_id)
        return index.search(normalized_query, limit=limit, k1=self.k1, b=self.b)
