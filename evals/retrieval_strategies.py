"""Retrieval strategy definitions for eval pipeline composition.

Demonstrates how to combine the exposed retrieval functions to test different strategies:
- BM25 only
- Dense only
- BM25 + Dense (no RRF/rerank)
- BM25 + Dense + RRF (no rerank)
- BM25 + Dense + RRF + Rerank (full hybrid)

Each strategy is a callable that takes (user_id, query, context_dict, limit) and returns results.
The context_dict provides dependencies: embedding_provider, vector_store, sparse_retriever, reranker.
"""
from __future__ import annotations

from typing import Any, Callable

from backend.app.domain.query_retrieval.hybrid_retriever import (
    fetch_dense_embeddings,
    fetch_sparse_results,
    apply_reranking,
    fuse_candidates,
)


StrategyFn = Callable[[str, str, dict[str, Any], int], list[dict[str, Any]]]


def bm25_only(user_id: str, query: str, context: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    """BM25-only retrieval (sparse search only)."""
    sparse_retriever = context.get("sparse_retriever")
    if not sparse_retriever:
        raise ValueError("sparse_retriever required for bm25_only strategy")
    
    return fetch_sparse_results(
        user_id=user_id,
        query=query,
        sparse_retriever=sparse_retriever,
        k=limit,
    )


def dense_only(user_id: str, query: str, context: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    """Dense embedding-only retrieval (semantic search only)."""
    embedding_provider = context.get("embedding_provider")
    vector_store = context.get("vector_store")
    if not embedding_provider or not vector_store:
        raise ValueError("embedding_provider and vector_store required for dense_only strategy")
    
    return fetch_dense_embeddings(
        user_id=user_id,
        query=query,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        k=limit,
    )


def bm25_plus_dense_no_fusion(
    user_id: str, query: str, context: dict[str, Any], limit: int = 5
) -> list[dict[str, Any]]:
    """Concatenate BM25 + Dense results without fusion/ranking."""
    sparse_retriever = context.get("sparse_retriever")
    embedding_provider = context.get("embedding_provider")
    vector_store = context.get("vector_store")
    
    if not sparse_retriever or not embedding_provider or not vector_store:
        raise ValueError("sparse_retriever, embedding_provider, vector_store required")
    
    sparse_results = fetch_sparse_results(user_id, query, sparse_retriever, k=limit)
    dense_results = fetch_dense_embeddings(user_id, query, embedding_provider, vector_store, k=limit)
    
    # Simple concatenation, deduplicate by note_id.
    seen = set()
    combined = []
    for result in sparse_results + dense_results:
        note_id = str(result.get("note_id") or "")
        if note_id and note_id not in seen:
            combined.append(result)
            seen.add(note_id)
    
    return combined[:limit]


def bm25_plus_dense_with_rrf(
    user_id: str, query: str, context: dict[str, Any], limit: int = 5, rrf_k: int = 60
) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion (RRF) of BM25 + Dense (no rerank)."""
    sparse_retriever = context.get("sparse_retriever")
    embedding_provider = context.get("embedding_provider")
    vector_store = context.get("vector_store")
    
    if not sparse_retriever or not embedding_provider or not vector_store:
        raise ValueError("sparse_retriever, embedding_provider, vector_store required")
    
    sparse_results = fetch_sparse_results(user_id, query, sparse_retriever, k=limit)
    dense_results = fetch_dense_embeddings(user_id, query, embedding_provider, vector_store, k=limit)
    
    return fuse_candidates(
        candidate_lists=[
            ("sparse", sparse_results),
            ("original", dense_results),
        ],
        limit=limit,
        rrf_k=rrf_k,
    )


def bm25_plus_dense_with_rrf_and_rerank(
    user_id: str,
    query: str,
    context: dict[str, Any],
    limit: int = 5,
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    """Full hybrid: BM25 + Dense + RRF + Reranking."""
    sparse_retriever = context.get("sparse_retriever")
    embedding_provider = context.get("embedding_provider")
    vector_store = context.get("vector_store")
    reranker = context.get("reranker")
    
    if not sparse_retriever or not embedding_provider or not vector_store:
        raise ValueError("sparse_retriever, embedding_provider, vector_store required")
    
    sparse_results = fetch_sparse_results(user_id, query, sparse_retriever, k=limit)
    dense_results = fetch_dense_embeddings(user_id, query, embedding_provider, vector_store, k=limit)
    
    fused_candidates = fuse_candidates(
        candidate_lists=[
            ("sparse", sparse_results),
            ("original", dense_results),
        ],
        limit=limit,
        rrf_k=rrf_k,
    )
    
    return apply_reranking(query, fused_candidates, reranker, limit=limit)


# Strategy registry for easy eval iteration.
STRATEGIES: dict[str, StrategyFn] = {
    "bm25_only": bm25_only,
    "dense_only": dense_only,
    "bm25_plus_dense_no_fusion": bm25_plus_dense_no_fusion,
    "bm25_plus_dense_rrf": bm25_plus_dense_with_rrf,
    "bm25_plus_dense_rrf_rerank": bm25_plus_dense_with_rrf_and_rerank,
}


def run_strategy(
    strategy_name: str,
    user_id: str,
    query: str,
    context: dict[str, Any],
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Execute a named strategy."""
    if strategy_name not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy_name}. Available: {list(STRATEGIES.keys())}")
    
    return STRATEGIES[strategy_name](user_id, query, context, limit)
