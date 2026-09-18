from __future__ import annotations

import os
import re
from typing import Any

from ..constants import GENERIC_QUERY_TERMS, NEGATION_TERMS
from ..memory.services import query_recent_memory_for_user
from ..ports import QueryRewriter
from ...infrastructure.llm.prompt_logger import append_pipeline_log
from ...infrastructure.llm.query_rewriter import get_query_rewriter
from .utils import tokenize
from .hybrid_retriever import get_hybrid_retriever


MIN_QUERY_QUALITY_TO_REWRITE = float(os.getenv("QUERY_REWRITE_MIN_QUERY_QUALITY", "0.35"))
MIN_REWRITE_CONFIDENCE = float(os.getenv("QUERY_REWRITE_MIN_CONFIDENCE", "0.55"))
DEFAULT_QUERY_LIMIT = int(os.getenv("QUERY_RETRIEVAL_TOP_K", "5"))


def retrieve_query_context(
    user_id: str,
    query: str,
    limit: int = DEFAULT_QUERY_LIMIT,
    query_rewriter: QueryRewriter | None = None,
) -> dict[str, Any]:
    """Orchestrate chat's query rewrite + hybrid retrieval flow.
    
    Chat-only concerns: query quality scoring, rewrite decision, risk detection.
    Delegates the actual ranked retrieval to HybridRetriever.
    """
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

    # Chat-only: evaluate query quality and decide whether to attempt rewrite.
    query_quality = score_query_quality(normalized_query)
    rewrite_used = False
    fallback_reason: str | None = None
    rewritten_query: str | None = None
    likely_answer: str | None = None
    rewrite_confidence: float | None = None
    rewrite_risk_flags: list[str] = []
    alternate_query_text: str | None = None

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
                alternate_query_text = " ".join(
                    part for part in [normalized_query, rewritten_query, likely_answer] if part
                ).strip()
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

    # Delegate the actual hybrid fetch to HybridRetriever.
    hybrid_retriever = get_hybrid_retriever()
    candidates = hybrid_retriever.fetch(
        user_id=user_id,
        query_text=normalized_query,
        limit=clamped_limit,
        alternate_query_text=alternate_query_text if rewrite_used else None,
    )

    return {
        "original_query": normalized_query,
        "rewritten_query": rewritten_query if rewrite_used else None,
        "likely_answer": likely_answer if rewrite_used else None,
        "rewrite_confidence": rewrite_confidence,
        "rewrite_used": rewrite_used,
        "fallback_reason": fallback_reason,
        "rerank_used": candidates[0].get("rerank_score") is not None if candidates else False,
        "rerank_strategy": None,  # Rerank strategy is now handled inside HybridRetriever
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


def shorten_text(text: str, limit: int = 96) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3].rstrip()}..."
