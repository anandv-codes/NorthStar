"""Consolidated hybrid retrieval pipeline for both chat and note-ingestion.

Combines BM25 (sparse) + dense embeddings + RRF fusion + optional reranking.

EVAL COMPOSITION:
  Individual retrieval functions are exposed as public building blocks for eval pipelines:
  - fetch_dense_embeddings(user_id, query, embedding_provider, vector_store, k)
  - fetch_sparse_results(user_id, query, sparse_retriever, k)
  - apply_reranking(query, candidates, reranker, limit)
  - fuse_candidates(candidate_lists, limit, rrf_k) [utility for combining results]
  - summarize_top_sources(candidates, limit) [diagnostic summary]
  
  Eval pipeline example:
    dense_results = fetch_dense_embeddings(user_id, query, emb_provider, vs, k=5)
    sparse_results = fetch_sparse_results(user_id, query, bm25, k=5)
    fused = fuse_candidates([("dense", dense_results), ("sparse", sparse_results)], limit=5)
    final = apply_reranking(query, fused, reranker, limit=5)  # optional

PRODUCTION USAGE:
  - retrieve_query_context (chat's similarity search wrapper)
  - fetch_related_context (note-ingestion's context-gathering wrapper)
"""
from __future__ import annotations

import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Sequence

from ..ports import EmbeddingProvider, VectorStore
from .strategies.base import BaseRetrieval
from .reranker.base import BaseReranker
from .reranker.semantic import SentenceTransformerReranker
from .strategies.sparse import SparseBM25Retriever
from ...infrastructure.llm.prompt_logger import append_pipeline_log, elapsed_ms
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


# Alias for eval composition (public API).
summarize_top_sources = _summarize_top_sources


# ============================================================================
# CORE RETRIEVAL FUNCTIONS (for eval composition)
# ============================================================================


def fetch_dense_embeddings(
    user_id: str,
    query: str,
    embedding_provider: EmbeddingProvider,
    vector_store: VectorStore,
    k: int = 5,
) -> list[dict[str, Any]]:
    """
    Fetch results via dense (embedding-based) semantic search.
    
    Args:
        user_id: User identifier for scoped search.
        query: Query text to embed and search.
        embedding_provider: Provider for query embedding (e.g., SentenceTransformers).
        vector_store: Vector store for similarity search (e.g., Chroma).
        k: Number of results to return.
    
    Returns:
        List of result dicts with note_id, text, summary, distance, etc.
    """
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return []
    
    clamped_k = max(1, min(k, 20))
    embedding = embedding_provider.embed_query(normalized_query)
    results = vector_store.query_related_notes(user_id=user_id, embedding=embedding, k=clamped_k)
    return results


def fetch_sparse_results(
    user_id: str,
    query: str,
    sparse_retriever: BaseRetrieval,
    k: int = 5,
) -> list[dict[str, Any]]:
    """
    Fetch results via sparse (BM25) retrieval.
    
    Args:
        user_id: User identifier for scoped search.
        query: Query text for BM25 matching.
        sparse_retriever: Sparse retriever implementation (e.g., SparseBM25Retriever).
        k: Number of results to return.
    
    Returns:
        List of result dicts with note_id, text, summary, distance, etc.
    """
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return []
    
    clamped_k = max(1, min(k, 20))
    results = sparse_retriever.retrieve(query=normalized_query, user_id=user_id, limit=clamped_k)
    return results


def apply_reranking(
    query: str,
    candidates: list[dict[str, Any]],
    reranker: BaseReranker | None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Optional reranking step (if reranker is provided).
    
    Args:
        query: Query text for reranking context.
        candidates: List of candidate dicts to rerank.
        reranker: Reranker implementation (None = skip reranking).
        limit: Maximum results to return after reranking.
    
    Returns:
        List of reranked results (or input candidates if reranker is None).
    """
    if reranker is None or not candidates:
        return candidates
    
    clamped_limit = max(1, min(limit, 20))
    return reranker.rerank(query, candidates, limit=clamped_limit)


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
        
        Internally composes: fetch_dense_embeddings + fetch_sparse_results + fuse_candidates + apply_reranking.
        
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
        expanded_query = str(alternate_query_text or "").strip()

        def _fetch_dense_original() -> list[dict[str, Any]]:
            stage_start = time.perf_counter()
            results = fetch_dense_embeddings(
                user_id=user_id,
                query=normalized_query,
                embedding_provider=self.embedding_provider,
                vector_store=self.vector_store,
                k=clamped_limit,
            )
            append_pipeline_log(
                "hybrid retrieval",
                [
                    f"semantic search returned {len(results)} result(s)",
                    f"elapsed_ms: {elapsed_ms(stage_start):.1f}",
                ],
            )
            return results

        def _fetch_sparse() -> list[dict[str, Any]]:
            stage_start = time.perf_counter()
            results = fetch_sparse_results(
                user_id=user_id,
                query=normalized_query,
                sparse_retriever=self.sparse_retriever,
                k=clamped_limit,
            )
            append_pipeline_log(
                "hybrid retrieval",
                [
                    f"bm25 returned {len(results)} result(s)",
                    f"elapsed_ms: {elapsed_ms(stage_start):.1f}",
                ],
            )
            return results

        def _fetch_dense_rewritten() -> list[dict[str, Any]]:
            stage_start = time.perf_counter()
            results = fetch_dense_embeddings(
                user_id=user_id,
                query=expanded_query,
                embedding_provider=self.embedding_provider,
                vector_store=self.vector_store,
                k=clamped_limit,
            )
            append_pipeline_log(
                "hybrid retrieval",
                [
                    f"alternate query search returned {len(results)} result(s)",
                    f"elapsed_ms: {elapsed_ms(stage_start):.1f}",
                ],
            )
            return results

        # Dense-original, sparse (BM25), and dense-rewritten searches are
        # mutually independent — run them concurrently instead of one after
        # another. Exceptions still propagate via .result() below, same as
        # the prior sequential calls would have raised.
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                "dense_original": executor.submit(_fetch_dense_original),
                "sparse": executor.submit(_fetch_sparse),
            }
            if expanded_query:
                futures["rewritten"] = executor.submit(_fetch_dense_rewritten)

            dense_original_results = futures["dense_original"].result()
            sparse_results = futures["sparse"].result()
            rewritten_results: list[dict[str, Any]] = (
                futures["rewritten"].result() if "rewritten" in futures else []
            )

        # RRF fusion.
        stage_start = time.perf_counter()
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
                f"elapsed_ms: {elapsed_ms(stage_start):.1f}",
            ],
        )

        # Optional reranking.
        stage_start = time.perf_counter()
        candidates = apply_reranking(
            query=normalized_query,
            candidates=candidates,
            reranker=self.reranker,
            limit=clamped_limit,
        )
        if self.reranker is not None:
            append_pipeline_log(
                "hybrid retrieval",
                [
                    f"reranking returned {len(candidates)} result(s)",
                    f"rerank strategy: {RERANKER_MODE}",
                    f"elapsed_ms: {elapsed_ms(stage_start):.1f}",
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
