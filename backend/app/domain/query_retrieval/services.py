from __future__ import annotations

import os
import re
from collections import defaultdict
from typing import Any, Sequence

from ..constants import GENERIC_QUERY_TERMS, NEGATION_TERMS
from ..memory.services import query_recent_memory_for_user
from ..ports import EmbeddingProvider, QueryRewriter, VectorStore
from ...infrastructure.llm.prompt_logger import append_pipeline_log
from ...infrastructure.llm.query_rewriter import get_query_rewriter
from .reranker.semantic import SentenceTransformerReranker
from .strategies.sparse import SparseBM25Retriever
from .utils import tokenize
from ...infrastructure.vector.embeddings import get_embedding_provider
from ...infrastructure.vector.vectorstore import get_vector_store



MIN_QUERY_QUALITY_TO_REWRITE = float(os.getenv("QUERY_REWRITE_MIN_QUERY_QUALITY", "0.35"))
MIN_REWRITE_CONFIDENCE = float(os.getenv("QUERY_REWRITE_MIN_CONFIDENCE", "0.55"))
DEFAULT_QUERY_LIMIT = int(os.getenv("QUERY_RETRIEVAL_TOP_K", "5"))
RRF_K = int(os.getenv("QUERY_RETRIEVAL_RRF_K", "60"))
RERANKER_MODE = os.getenv("QUERY_RETRIEVAL_RERANKER", "semantic").strip().lower()
SPARSE_RETRIEVER = SparseBM25Retriever()
RERANKER = SentenceTransformerReranker() if RERANKER_MODE in {"semantic", "sentence", "cross", "local", "true", "1", "yes", "on"} else None


def retrieve_query_context(
    user_id: str,
    query: str,
    limit: int = DEFAULT_QUERY_LIMIT,
    embedding_provider: EmbeddingProvider | None = None,
    vector_store: VectorStore | None = None,
    query_rewriter: QueryRewriter | None = None,
) -> dict[str, Any]:
    embedding_provider = embedding_provider or get_embedding_provider()
    vector_store = vector_store or get_vector_store()
    query_rewriter = query_rewriter or get_query_rewriter()

    normalized_query = str(query or "").strip()
    if not normalized_query:
        raise ValueError("query is required")

    clamped_limit = max(1, min(limit, 20))
    recent_memory = query_recent_memory_for_user(user_id=user_id, limit=min(5, clamped_limit))
    append_pipeline_log(
        "hybrid retrieval",
        [
            "planning hybrid retrieval",
            f"query: {shorten_text(normalized_query)}",
            f"limit: {clamped_limit}",
        ],
    )


    embeddings = embedding_provider
    original_embedding = embeddings.embed_query(normalized_query)
    dense_original_results = vector_store.query_related_notes(
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
    sparse_results = SPARSE_RETRIEVER.retrieve(
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

    query_quality = score_query_quality(normalized_query)
    rewrite_used = False
    fallback_reason: str | None = None
    rewritten_query: str | None = None
    likely_answer: str | None = None
    rewrite_confidence: float | None = None
    rewrite_risk_flags: list[str] = []
    rewritten_results: list[dict[str, Any]] = []

    if query_quality >= MIN_QUERY_QUALITY_TO_REWRITE:
        try:
            rewrite_result = query_rewriter.rewrite(
                user_query=normalized_query,
                recent_memory=recent_memory,
            )
            rewritten_query = rewrite_result.get("rewritten_query") or normalized_query
            likely_answer = rewrite_result.get("likely_answer") or ""
            rewrite_confidence = float(rewrite_result.get("confidence") or 0.0)
            rewrite_risk_flags = detect_rewrite_risks(
                original_query=normalized_query,
                rewritten_query=rewritten_query,
                likely_answer=likely_answer,
                llm_flags=rewrite_result.get("risk_flags") or [],
            )
            if rewrite_confidence >= MIN_REWRITE_CONFIDENCE and not rewrite_risk_flags:
                rewrite_used = True
                expanded_query = " ".join(
                    part for part in [normalized_query, rewritten_query, likely_answer] if part
                ).strip()
                rewritten_embedding = embeddings.embed_query(expanded_query)
                rewritten_results = vector_store.query_related_notes(
                    user_id=user_id,
                    embedding=rewritten_embedding,
                    k=clamped_limit,
                )
                append_pipeline_log(
                    "hybrid retrieval",
                    [
                        f"rewrite retrieval returned {len(rewritten_results)} result(s)",
                    ],
                )
            else:
                fallback_reason = "rewrite_confidence_or_risk_threshold"
                append_pipeline_log(
                    "hybrid retrieval",
                    [
                        f"rewrite skipped: {fallback_reason}",
                    ],
                )
        except RuntimeError as exc:
            fallback_reason = str(exc)
            append_pipeline_log(
                "hybrid retrieval",
                [
                    f"rewrite skipped: {fallback_reason}",
                ],
            )
    else:
        fallback_reason = "low_query_quality"
        append_pipeline_log(
            "hybrid retrieval",
            [
                f"rewrite skipped: {fallback_reason}",
            ],
        )

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

    rerank_used = False
    rerank_strategy: str | None = None
    if RERANKER is not None and candidates:
        candidates = RERANKER.rerank(normalized_query, candidates, limit=clamped_limit)
        rerank_used = True
        rerank_strategy = RERANKER_MODE
        append_pipeline_log(
            "hybrid retrieval",
            [
                f"reranking returned {len(candidates)} result(s)",
                f"rerank strategy: {rerank_strategy}",
            ],
        )
    else:
        append_pipeline_log(
            "hybrid retrieval",
            [
                "reranking skipped",
            ],
        )

    return {
        "original_query": normalized_query,
        "rewritten_query": rewritten_query if rewrite_used else None,
        "likely_answer": likely_answer if rewrite_used else None,
        "rewrite_confidence": rewrite_confidence,
        "rewrite_used": rewrite_used,
        "fallback_reason": fallback_reason,
        "rerank_used": rerank_used,
        "rerank_strategy": rerank_strategy,
        "candidates": candidates,
    }


def score_query_quality(query: str) -> float:
    tokens = tokenize(query)
    if not tokens:
        return 0.0

    score = min(len(tokens) / 6.0, 1.0)

    lowered = query.lower()
    if any(char.isdigit() for char in query):
        score += 0.2
    if any(term in lowered for term in NEGATION_TERMS):
        score += 0.1
    if len(query.strip()) <= 12:
        score -= 0.15
    if len(tokens) <= 2:
        score -= 0.25
    if is_generic_query(tokens):
        score -= 0.2

    return max(0.0, min(score, 1.0))


def is_generic_query(tokens: list[str]) -> bool:
    return len(tokens) <= 3 and all(token in GENERIC_QUERY_TERMS for token in tokens)


def numeric_tokens(text: str) -> set[str]:
    return set(re.findall(r"\d+", text.lower()))


def detect_rewrite_risks(
    original_query: str,
    rewritten_query: str,
    likely_answer: str,
    llm_flags: list[str] | None = None,
) -> list[str]:
    risks = set(str(flag).strip() for flag in (llm_flags or []) if str(flag).strip())

    original_numbers = numeric_tokens(original_query)
    rewritten_numbers = numeric_tokens(f"{rewritten_query} {likely_answer}")
    if original_numbers and not original_numbers.issubset(rewritten_numbers):
        risks.add("missing_number")

    original_negation = any(term in original_query.lower() for term in NEGATION_TERMS)
    rewritten_negation = any(
        term in f"{rewritten_query} {likely_answer}".lower() for term in NEGATION_TERMS
    )
    if original_negation and not rewritten_negation:
        risks.add("negation_lost")

    original_tokens = set(tokenize(original_query))
    rewritten_tokens = set(tokenize(f"{rewritten_query} {likely_answer}"))
    if original_tokens and not original_tokens.intersection(rewritten_tokens):
        risks.add("semantic_drift")

    if not rewritten_query.strip() and not likely_answer.strip():
        risks.add("empty_rewrite")

    return sorted(risks)


def fuse_candidates(
    candidate_lists: Sequence[tuple[str, list[dict[str, Any]]]],
    limit: int,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    scores: dict[str, float] = defaultdict(float)

    for source, results in candidate_lists:
        for rank, item in enumerate(results, start=1):
            note_id = str(item.get("note_id") or "").strip()
            if not note_id:
                continue

            scores[note_id] += 1.0 / (RRF_K + rank)
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
    top_candidates = candidates[:limit]
    bm25_backed = 0
    semantic_backed = 0
    blended = 0

    for candidate in top_candidates:
        sparse_hit = candidate.get("sparse_rank") is not None
        dense_hit = candidate.get("original_rank") is not None or candidate.get("rewritten_rank") is not None
        if sparse_hit and dense_hit:
            blended += 1
        elif sparse_hit:
            bm25_backed += 1
        elif dense_hit:
            semantic_backed += 1

    return (
        f"top {len(top_candidates)} docs: "
        f"{bm25_backed} bm25-backed, "
        f"{semantic_backed} semantic-backed, "
        f"{blended} blended"
    )


def shorten_text(text: str, limit: int = 96) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3].rstrip()}..."
