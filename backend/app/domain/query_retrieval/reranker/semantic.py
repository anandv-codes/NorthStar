from __future__ import annotations

from typing import Any
import os

from .base import BaseReranker


class SentenceTransformerReranker(BaseReranker):
    """
    Cross-encoder reranker using Sentence Transformers.
    Uses 'ms-marco-MiniLM-L-6-v2' trained on MS MARCO ranking dataset.
    """

    def __init__(self, model_name: str = "ms-marco-MiniLM-L-6-v2"):
        """Initialize the cross-encoder model."""
        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for SentenceTransformerReranker. "
                "Install with: pip install sentence-transformers"
            )
        
        self.model = CrossEncoder(model_name)
        self.model_name = model_name

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Rerank candidates using cross-encoder semantic similarity.
        
        Args:
            query: The search query
            candidates: List of candidate documents with 'text' field
            limit: Maximum number of results to return
            
        Returns:
            Reranked candidates sorted by semantic relevance
        """
        normalized_query = str(query or "").strip()
        if not normalized_query or not candidates:
            return candidates[:limit]

        # Extract candidate texts
        candidate_texts = []
        for candidate in candidates:
            text = " ".join(
                part
                for part in [
                    str(candidate.get("text") or ""),
                    str(candidate.get("summary") or ""),
                ]
                if part
            ).strip()
            candidate_texts.append(text)

        # Score candidates with cross-encoder
        try:
            scores = self.model.predict(
                [[normalized_query, text] for text in candidate_texts]
            )
        except Exception as e:
            # Fallback: return candidates as-is if ranking fails
            return candidates[:limit]

        # Attach scores to candidates
        scored_candidates: list[dict[str, Any]] = []
        for candidate, score in zip(candidates, scores):
            scored_candidate = dict(candidate)
            scored_candidate["rerank_score"] = float(score)
            scored_candidate["score"] = float(score)
            scored_candidates.append(scored_candidate)

        # Sort by rerank score (descending)
        scored_candidates.sort(
            key=lambda item: (
                -float(item.get("score") or 0.0),
                -float(item.get("rrf_score") or 0.0),
                str(item.get("note_id") or ""),
            )
        )

        return scored_candidates[:limit]
