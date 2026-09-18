"""Consolidated hybrid retrieval pipeline for both chat and note-ingestion.

Combines BM25 (sparse) + dense embeddings + RRF fusion + optional reranking.
Used by:
  - retrieve_query_context (chat's similarity search wrapper)
  - fetch_related_context (note-ingestion's context-gathering wrapper)
"""
from __future__ import annotations

import os
from collections import defaultdict
from typing import Any, Sequence

from ..ports import BaseReranker, BaseRetrieval, EmbeddingProvider, VectorStore
from .reranker.semantic import SentenceTransformerReranker
from .strategies.sparse import SparseBM25Retriever
from ...infrastructure.llm.prompt_logger import append_pipeline_log
from ...infrastructure.vector.embeddings import get_embedding_provider
from ...infrastructure.vector.vectorstore import get_vector_store


RRF_K = int(os.getenv("QUERY_RETRIEVAL_RRF_K", "60"))
RERANKER_MODE = os.getenv("QUERY_RETRIEVAL_RERANKER", "semantic").strip().lower()


def fuse_candidates(
    candidate_lists: Sequence[tuple[str, list[dict[str, Any]]]],
    limit: int,
    rrf_k: int = RRF_K,
) -> list[dict[str, Any]]:
    """Fuse candidates from multiple retrieval sources using Reciprocal Rank Fusion (RRF)."""
    merged: dict[str, dict[str, Any]] = {}
    scores: dict[str, float] = defaultdict(float)

    for source, results in candidate_lists:
        for rank, item in enumerate(results, start=1):
            note_id = str(item.get("note_id") or "").strip()
            if not note_id:
                continue

            scores[note_id] += 1.0 / (rrf_k + rank)
            existing = merged.setdefault(
                note_id,
                {
                    "note_id": note_id,
                    "text": item.get("text", ""),
                    "summary": item.get("summary"),
                    "sparse_distance": None,
                    "sparse_rank": None,
                    "original_distance": None,
                    "original_rank": None,
                    "rewritten_distance": None,
                    "rewritten_rank": None,
                    "rrf_score": 0.0,
                    "rerank_score": None,
                    "score": 0.0,
                },
            )

            if source == "sparse":
                existing["sparse_rank"] = rank
                existing["sparse_distance"] = item.get("distance")
            elif source == "original":
                existing["original_rank"] = rank
                existing["original_distance"] = item.get("distance")
            elif source == "rewritten":
                existing["rewritten_rank"] = rank
                existing["rewritten_distance"] = item.get("distance")

            if not existing.get("text"):
                existing["text"] = item.get("text", "")
            if existing.get("summary") is None:
                existing["summary"] = item.get("summary")

    for note_id, score in scores.items():
        if note_id in merged:
            merged[note_id]["rrf_score"] = score
            merged[note_id]["score"] = score

    ordered = sorted(
        merged.values(),
        key=lambda item: (
            -float(item.get("score") or 0.0),
            -sum(1 for key in ("sparse_rank", "original_rank", "rewritten_rank") if item.get(key) is not None),
            item.get("sparse_rank") if item.get("sparse_rank") is not None else 9999,
            item.get("original_rank") if item.get("original_rank") is not None else 9999,
            item.get("rewritten_rank") if item.get("rewritten_rank") is not None else 9999,
            str(item.get("note_id") or ""),
        ),
    )
    return ordered[:limit]


def _summarize_top_sources(candidates: list[dict[str, Any]], limit: int) -> str:
    """Generate a summary of which retrieval sources contributed to the top results."""
    top_candidates = candidates[:limit]
    bm25_backed = 0
    semantic_backed = 0
    blended = 0

    for candidate in top_candidates:
        has_bm25 = candidate.get("sparse_rank") is not None
        has_semantic = candidate.get("original_rank") is not None or candidate.get("rewritten_rank") is not None

        if has_bm25 and has_semantic:
            blended += 1
        elif has_bm25:
            bm25_backed += 1
        elif has_semantic:
            semantic_backed += 1

    parts = []
    if bm25_backed:
        parts.append(f"{bm25_backed} BM25-only")
    if semantic_backed:
        parts.append(f"{semantic_backed} semantic-only")
    if blended:
        parts.append(f"{blended} blended")
    return f"Top sources: {', '.join(parts)}" if parts else "Top sources: none"


class HybridRetriever:
    """
    Core hybrid retrieval pipeline: BM25 + dense + optional rewrite + RRF + optional rerank.
    
    Single responsibility: fusion/ranking only. No query-rewrite logic, no note-specific logic.
    Used by both chat (via retrieve_query_context) and note-ingestion (via NoteContextRetriever).
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None = None,
        vector_store: VectorStore | None = None,
        sparse_retriever: BaseRetrieval | None = None,
        reranker: BaseReranker | None = None,
    ):
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.vector_store = vector_store or get_vector_store()
        self.sparse_retriever = sparse_retriever or SparseBM25Retriever()
        self.reranker = reranker or (
            SentenceTransformerReranker() 
            if RERANKER_MODE in {"semantic", "sentence", "cross", "local", "true", "1", "yes", "on"} 
            else None
        )

    def fetch(
        self,
        user_id: str,
        query_text: str,
        limit: int = 5,
        alternate_query_text: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch ranked results via hybrid retrieval.
        
        Args:
            user_id: User identifier for scoped search.
            query_text: Original query text (always searched).
            limit: Maximum results to return (1-20).
            alternate_query_text: Optional expanded/rewritten query (searched only if provided).
        
        Returns:
            List of ranked result dicts with note_id, text, summary, scoring info.
        """
        normalized_query = str(query_text or "").strip()
        if not normalized_query:
            return []

        clamped_limit = max(1, min(limit, 20))
        
        # Dense search on original query.
        original_embedding = self.embedding_provider.embed_query(normalized_query)
        dense_original_results = self.vector_store.query_related_notes(
            user_id=user_id,
            embedding=original_embedding,
            k=clamped_limit,
        )
        append_pipeline_log(
            "hybrid retrieval",
            [
                f"semantic search returned {len(dense_original_results)} result(s)",
            ],
        )

        # Sparse (BM25) search.
        sparse_results = self.sparse_retriever.retrieve(
            query=normalized_query,
            user_id=user_id,
            limit=clamped_limit,
        )
        append_pipeline_log(
            "hybrid retrieval",
            [
                f"bm25 returned {len(sparse_results)} result(s)",
            ],
        )

        # Dense search on alternate query, if provided.
        rewritten_results: list[dict[str, Any]] = []
        if alternate_query_text:
            expanded_query = str(alternate_query_text).strip()
            if expanded_query:
                rewritten_embedding = self.embedding_provider.embed_query(expanded_query)
                rewritten_results = self.vector_store.query_related_notes(
                    user_id=user_id,
                    embedding=rewritten_embedding,
                    k=clamped_limit,
                )
                append_pipeline_log(
                    "hybrid retrieval",
                    [
                        f"alternate query search returned {len(rewritten_results)} result(s)",
                    ],
                )

        # RRF fusion.
        candidates = fuse_candidates(
            candidate_lists=[
                ("sparse", sparse_results),
                ("original", dense_original_results),
                ("rewritten", rewritten_results),
            ],
            limit=clamped_limit,
        )
        append_pipeline_log(
            "hybrid retrieval",
            [
                f"fusion returned {len(candidates)} candidate(s)",
                _summarize_top_sources(candidates, clamped_limit),
            ],
        )

        # Optional reranking.
        if self.reranker is not None and candidates:
            candidates = self.reranker.rerank(normalized_query, candidates, limit=clamped_limit)
            append_pipeline_log(
                "hybrid retrieval",
                [
                    f"reranking returned {len(candidates)} result(s)",
                    f"rerank strategy: {RERANKER_MODE}",
                ],
            )
        else:
            append_pipeline_log(
                "hybrid retrieval",
                [
                    "reranking skipped",
                ],
            )

        return candidates


class NoteContextRetriever:
    """
    Thin wrapper for note-ingestion's context-gathering.
    
    Delegates to HybridRetriever; no rewrite logic. Used by note_processor.py to gather
    related notes before passing to LLM extraction prompt.
    """

    def __init__(self, hybrid_retriever: HybridRetriever | None = None):
        self.hybrid_retriever = hybrid_retriever or get_hybrid_retriever()

    def fetch_related_context(
        self,
        user_id: str,
        raw_text: str,
        limit: int = 3,
        exclude_note_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch related notes for a new note being processed.
        
        Args:
            user_id: User identifier.
            raw_text: New note's raw text to search for related context.
            limit: Maximum related notes to return.
            exclude_note_id: Note ID to exclude from results (the note being processed).
        
        Returns:
            List of ranked related-note dicts.
        """
        # No rewrite for note-ingestion; just fetch using the raw text as-is.
        results = self.hybrid_retriever.fetch(
            user_id=user_id,
            query_text=raw_text,
            limit=limit,
            alternate_query_text=None,
        )
        
        # Filter out self-reference if specified.
        if exclude_note_id:
            results = [r for r in results if str(r.get("note_id") or "") != str(exclude_note_id)]
        
        return results


# Module-level singletons.
_HYBRID_RETRIEVER_INSTANCE: HybridRetriever | None = None
_NOTE_CONTEXT_RETRIEVER_INSTANCE: NoteContextRetriever | None = None


def get_hybrid_retriever() -> HybridRetriever:
    """Singleton factory for HybridRetriever."""
    global _HYBRID_RETRIEVER_INSTANCE
    if _HYBRID_RETRIEVER_INSTANCE is None:
        _HYBRID_RETRIEVER_INSTANCE = HybridRetriever()
    return _HYBRID_RETRIEVER_INSTANCE


def get_note_context_retriever() -> NoteContextRetriever:
    """Singleton factory for NoteContextRetriever."""
    global _NOTE_CONTEXT_RETRIEVER_INSTANCE
    if _NOTE_CONTEXT_RETRIEVER_INSTANCE is None:
        _NOTE_CONTEXT_RETRIEVER_INSTANCE = NoteContextRetriever()
    return _NOTE_CONTEXT_RETRIEVER_INSTANCE
