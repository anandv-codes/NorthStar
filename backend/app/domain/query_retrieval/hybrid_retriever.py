"""Consolidated hybrid retrieval pipeline for chat and note-ingestion.

Combines BM25 (sparse) + dense embeddings + exact-identifier matching + RRF
fusion + optional reranking.

The production entry point is ``HybridRetriever.retrieve(RetrievalRequest)``.
Task-specific policy (rewrite, entity expansion, stored-context reuse) belongs
in the calling service; this module only fetches, fuses, and ranks.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Mapping, Sequence

from ..ports import EmbeddingProvider, VectorStore
from .contracts import RetrievalRequest, RetrievalResult
from .strategies.base import BaseRetrieval
from .reranker.base import BaseReranker
from .reranker.semantic import SentenceTransformerReranker
from .utils import extract_identifiers
from ...infrastructure.llm.prompt_logger import append_pipeline_log, elapsed_ms
from ...infrastructure.vector.embeddings import get_embedding_provider
from ...infrastructure.vector.vectorstore import get_vector_store


RRF_K = int(os.getenv("QUERY_RETRIEVAL_RRF_K", "60"))
RERANKER_MODE = os.getenv("QUERY_RETRIEVAL_RERANKER", "off").strip().lower()
CANDIDATE_MULTIPLIER = float(os.getenv("QUERY_RETRIEVAL_CANDIDATE_MULTIPLIER", "3"))
EXACT_IDENTIFIER_WEIGHT = float(os.getenv("QUERY_RETRIEVAL_EXACT_ID_WEIGHT", "3"))


def _clamp_limit(value: int) -> int:
    return max(1, min(int(value), 20))


def fuse_candidates(
    candidate_lists: Sequence[tuple[str, list[dict[str, Any]]]],
    limit: int,
    rrf_k: int = RRF_K,
    weights: Mapping[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Fuse candidates from multiple retrieval sources using Reciprocal Rank Fusion."""
    merged: dict[str, dict[str, Any]] = {}
    scores: dict[str, float] = defaultdict(float)
    source_weights = dict(weights or {})

    for source, results in candidate_lists:
        weight = float(source_weights.get(source, 1.0))
        for rank, item in enumerate(results, start=1):
            note_id = str(item.get("note_id") or "").strip()
            if not note_id:
                continue

            scores[note_id] += weight / (rrf_k + rank)
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
                    "exact_distance": None,
                    "exact_rank": None,
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
            elif source == "exact":
                existing["exact_rank"] = rank
                existing["exact_distance"] = item.get("distance")

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
            # An exact identifier hit wins score ties against generic channels.
            item.get("exact_rank") if item.get("exact_rank") is not None else 9999,
            -sum(
                1
                for key in ("exact_rank", "sparse_rank", "original_rank", "rewritten_rank")
                if item.get(key) is not None
            ),
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
    exact_backed = 0
    blended = 0

    for candidate in top_candidates:
        has_exact = candidate.get("exact_rank") is not None
        has_bm25 = candidate.get("sparse_rank") is not None
        has_semantic = candidate.get("original_rank") is not None or candidate.get("rewritten_rank") is not None

        source_count = sum((has_exact, has_bm25, has_semantic))
        if source_count > 1:
            blended += 1
        elif has_exact:
            exact_backed += 1
        elif has_bm25:
            bm25_backed += 1
        elif has_semantic:
            semantic_backed += 1

    parts = []
    if exact_backed:
        parts.append(f"{exact_backed} exact-only")
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
    exclude_note_id: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch results via dense (embedding-based) semantic search."""
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return []

    clamped_k = _clamp_limit(k)
    embedding = embedding_provider.embed_query(normalized_query)
    return vector_store.query_related_notes(
        user_id=user_id,
        embedding=embedding,
        k=clamped_k,
        exclude_note_id=exclude_note_id,
    )


def fetch_sparse_results(
    user_id: str,
    query: str,
    sparse_retriever: BaseRetrieval,
    k: int = 5,
    exclude_note_id: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch results via sparse (BM25) retrieval."""
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return []

    return sparse_retriever.retrieve(
        query=normalized_query,
        user_id=user_id,
        limit=_clamp_limit(k),
        exclude_note_id=exclude_note_id,
    )


def fetch_exact_results(
    user_id: str,
    query: str,
    sparse_retriever: BaseRetrieval,
    k: int = 5,
    exclude_note_id: str | None = None,
    identifiers: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch exact identifier matches, if the sparse retriever supports them."""
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return []

    if identifiers is None:
        identifiers = extract_identifiers(normalized_query)
    if not identifiers:
        return []

    retrieve_exact = getattr(sparse_retriever, "retrieve_exact_identifiers", None)
    if not callable(retrieve_exact):
        return []
    return retrieve_exact(
        query=normalized_query,
        user_id=user_id,
        limit=_clamp_limit(k),
        exclude_note_id=exclude_note_id,
    )


def apply_reranking(
    query: str,
    candidates: list[dict[str, Any]],
    reranker: BaseReranker | None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Optionally rerank candidates; always enforce the final limit."""
    clamped_limit = _clamp_limit(limit)
    if reranker is None or not candidates:
        return candidates[:clamped_limit]
    return reranker.rerank(query, candidates, limit=clamped_limit)


class HybridRetriever:
    """Core hybrid retrieval pipeline: BM25 + dense + exact IDs + RRF + rerank."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None = None,
        vector_store: VectorStore | None = None,
        sparse_retriever: BaseRetrieval | None = None,
        reranker: BaseReranker | None = None,
    ):
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.vector_store = vector_store or get_vector_store()
        if sparse_retriever is None:
            from .strategies.sparse import SparseBM25Retriever

            sparse_retriever = SparseBM25Retriever()
        self.sparse_retriever = sparse_retriever
        self.reranker = reranker or (
            SentenceTransformerReranker()
            if RERANKER_MODE in {"semantic", "sentence", "cross", "local", "true", "1", "yes", "on"}
            else None
        )

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        """Retrieve and rank notes according to a task-independent request."""
        normalized_query = str(request.query or "").strip()
        if not normalized_query:
            return RetrievalResult(request=request)

        limit = request.clamped_limit
        candidate_limit = request.candidate_depth(CANDIDATE_MULTIPLIER)
        expanded_query = str(request.alternate_query or "").strip()
        identifiers = (
            extract_identifiers(normalized_query)
            if request.include_exact_identifiers
            else []
        )

        def _fetch_dense_original() -> list[dict[str, Any]]:
            stage_start = time.perf_counter()
            results = fetch_dense_embeddings(
                user_id=request.user_id,
                query=normalized_query,
                embedding_provider=self.embedding_provider,
                vector_store=self.vector_store,
                k=candidate_limit,
                exclude_note_id=request.exclude_note_id,
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
                user_id=request.user_id,
                query=normalized_query,
                sparse_retriever=self.sparse_retriever,
                k=candidate_limit,
                exclude_note_id=request.exclude_note_id,
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
                user_id=request.user_id,
                query=expanded_query,
                embedding_provider=self.embedding_provider,
                vector_store=self.vector_store,
                k=candidate_limit,
                exclude_note_id=request.exclude_note_id,
            )
            append_pipeline_log(
                "hybrid retrieval",
                [
                    f"alternate query search returned {len(results)} result(s)",
                    f"elapsed_ms: {elapsed_ms(stage_start):.1f}",
                ],
            )
            return results

        # Dense-original, sparse, and dense-rewritten searches are independent.
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

        # Exact identifiers are a deterministic channel, not a similarity guess.
        exact_results = fetch_exact_results(
            user_id=request.user_id,
            query=normalized_query,
            sparse_retriever=self.sparse_retriever,
            k=candidate_limit,
            exclude_note_id=request.exclude_note_id,
            identifiers=identifiers,
        )
        if identifiers:
            append_pipeline_log(
                "hybrid retrieval",
                [
                    f"exact identifier(s): {', '.join(identifiers)}",
                    f"exact matches returned {len(exact_results)} result(s)",
                ],
            )

        stage_start = time.perf_counter()
        candidates = fuse_candidates(
            candidate_lists=[
                ("exact", exact_results),
                ("sparse", sparse_results),
                ("original", dense_original_results),
                ("rewritten", rewritten_results),
            ],
            limit=candidate_limit,
            weights={"exact": EXACT_IDENTIFIER_WEIGHT},
        )
        append_pipeline_log(
            "hybrid retrieval",
            [
                f"fusion returned {len(candidates)} candidate(s) from depth {candidate_limit}",
                _summarize_top_sources(candidates, candidate_limit),
                f"elapsed_ms: {elapsed_ms(stage_start):.1f}",
            ],
        )

        stage_start = time.perf_counter()
        if request.rerank:
            candidates = apply_reranking(
                query=normalized_query,
                candidates=candidates,
                reranker=self.reranker,
                limit=limit,
            )
        else:
            candidates = candidates[:limit]

        if self.reranker is not None and request.rerank:
            append_pipeline_log(
                "hybrid retrieval",
                [
                    f"reranking returned {len(candidates)} result(s)",
                    f"rerank strategy: {RERANKER_MODE}",
                    f"elapsed_ms: {elapsed_ms(stage_start):.1f}",
                ],
            )
        else:
            append_pipeline_log("hybrid retrieval", ["reranking skipped"])

        return RetrievalResult(
            request=request,
            candidates=candidates,
            source_counts={
                "exact": len(exact_results),
                "sparse": len(sparse_results),
                "dense_original": len(dense_original_results),
                "dense_rewritten": len(rewritten_results),
            },
            exact_identifiers=identifiers,
        )

    def fetch(
        self,
        user_id: str,
        query_text: str,
        limit: int = 5,
        alternate_query_text: str | None = None,
        exclude_note_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Backward-compatible list-only wrapper around :meth:`retrieve`."""
        request = RetrievalRequest(
            user_id=user_id,
            query=query_text,
            limit=limit,
            alternate_query=alternate_query_text,
            exclude_note_id=exclude_note_id,
        )
        return self.retrieve(request).candidates


class NoteContextRetriever:
    """Thin ingestion policy: hybrid retrieval, no rewrite, exclude the note."""

    def __init__(self, hybrid_retriever: HybridRetriever | None = None):
        self.hybrid_retriever = hybrid_retriever or get_hybrid_retriever()

    def fetch_related_context(
        self,
        user_id: str,
        raw_text: str,
        limit: int = 3,
        exclude_note_id: str | None = None,
    ) -> list[dict[str, Any]]:
        result = self.hybrid_retriever.retrieve(
            RetrievalRequest(
                user_id=user_id,
                query=raw_text,
                limit=limit,
                mode="note_ingestion",
                exclude_note_id=exclude_note_id,
            )
        )
        return result.candidates


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
