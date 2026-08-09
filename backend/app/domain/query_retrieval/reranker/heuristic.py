from __future__ import annotations

from typing import Any, List

from ..utils import tokenize
from .base import BaseReranker


class TokenOverlapReranker(BaseReranker):
    def rerank(self, query: str, candidates: List[dict[str, Any]], limit: int = 5) -> List[dict[str, Any]]:
        normalized_query = str(query or "").strip()
        if not normalized_query or not candidates:
            return candidates[:limit]

        query_tokens = tokenize(normalized_query)
        if not query_tokens:
            return candidates[:limit]

        query_token_set = set(query_tokens)
        scored_candidates: list[dict[str, Any]] = []

        for candidate in candidates:
            text = " ".join(
                part
                for part in [
                    str(candidate.get("text") or ""),
                    str(candidate.get("summary") or ""),
                ]
                if part
            ).strip()
            candidate_tokens = tokenize(text)
            candidate_token_set = set(candidate_tokens)

            if not candidate_token_set:
                rerank_score = float(candidate.get("score") or 0.0)
            else:
                overlap = len(query_token_set.intersection(candidate_token_set))
                coverage = overlap / float(len(query_token_set))
                density = overlap / float(len(candidate_token_set))
                phrase_bonus = 0.2 if normalized_query.lower() in text.lower() else 0.0
                rerank_score = coverage + density + phrase_bonus

            scored_candidate = dict(candidate)
            scored_candidate["rerank_score"] = rerank_score
            scored_candidate["score"] = rerank_score
            scored_candidates.append(scored_candidate)

        scored_candidates.sort(
            key=lambda item: (
                -float(item.get("score") or 0.0),
                -float(item.get("rrf_score") or 0.0),
                str(item.get("note_id") or ""),
            )
        )
        return scored_candidates[:limit]
