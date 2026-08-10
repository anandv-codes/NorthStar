from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from evals.metrics import foreign_result_ids, precision_at_k, recall_at_k


RetrieveCandidates = Callable[[str, str, int], Sequence[dict[str, Any]]]


def evaluate_retriever(
    cases: Sequence[dict[str, Any]],
    notes_by_user: dict[str, list[dict[str, Any]]],
    retrieve_candidates: RetrieveCandidates,
    k: int,
) -> tuple[list[dict[str, Any]], dict[str, int | float]]:
    """Score a retrieval callback against immutable evaluation cases."""
    case_results: list[dict[str, Any]] = []
    precision_scores: list[float] = []
    recall_scores: list[float] = []

    for case in cases:
        user_id = str(case["user_id"])
        retrieved = retrieve_candidates(str(case["query"]), user_id, k)
        retrieved_ids = [str(item["note_id"]) for item in retrieved]
        relevant_ids = [str(note_id) for note_id in case.get("relevant_note_ids", [])]
        allowed_ids = [str(note["note_id"]) for note in notes_by_user[user_id]]
        foreign_ids = foreign_result_ids(retrieved_ids, allowed_ids)
        is_no_context_case = not relevant_ids
        conflict = case.get("conflict") or {}
        conflict_ids = {str(note_id) for note_id in conflict.get("conflicting_note_ids", [])}

        result = {
            "id": case["id"],
            "query": case["query"],
            "user_id": user_id,
            "retrieved_note_ids": retrieved_ids,
            "relevant_note_ids": relevant_ids,
            "precision_at_k": None,
            "recall_at_k": None,
            "foreign_result_ids": foreign_ids,
            "isolation_passed": not foreign_ids,
            "no_context_passed": not retrieved_ids if is_no_context_case else None,
            "conflict_retrieval_complete": conflict_ids.issubset(retrieved_ids) if conflict_ids else None,
        }

        if not is_no_context_case:
            result["precision_at_k"] = precision_at_k(retrieved_ids, relevant_ids, k)
            result["recall_at_k"] = recall_at_k(retrieved_ids, relevant_ids, k)
            precision_scores.append(result["precision_at_k"])
            recall_scores.append(result["recall_at_k"])

        case_results.append(result)

    conflict_results = [
        result for result in case_results if result["conflict_retrieval_complete"] is not None
    ]
    summary: dict[str, int | float] = {
        "precision_at_k": sum(precision_scores) / len(precision_scores) if precision_scores else 0.0,
        "recall_at_k": sum(recall_scores) / len(recall_scores) if recall_scores else 0.0,
        "isolation_failure_count": sum(not result["isolation_passed"] for result in case_results),
        "no_context_pass_count": sum(result["no_context_passed"] is True for result in case_results),
        "no_context_case_count": sum(result["no_context_passed"] is not None for result in case_results),
        "conflict_retrieval_pass_count": sum(result["conflict_retrieval_complete"] is True for result in conflict_results),
        "conflict_case_count": len(conflict_results),
    }
    return case_results, summary