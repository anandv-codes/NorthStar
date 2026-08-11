from __future__ import annotations

from collections.abc import Iterable, Sequence


def precision_at_k(retrieved_ids: Sequence[str], relevant_ids: Iterable[str], k: int) -> float:
    """Return the fraction of the first k retrieved items that are relevant."""
    if k <= 0:
        raise ValueError("k must be greater than zero")

    top_k = list(retrieved_ids[:k])
    if not top_k:
        return 0.0

    relevant = set(relevant_ids)
    return sum(note_id in relevant for note_id in top_k) / len(top_k)


def recall_at_k(retrieved_ids: Sequence[str], relevant_ids: Iterable[str], k: int) -> float:
    """Return the proportion of relevant items present in the first k results."""
    if k <= 0:
        raise ValueError("k must be greater than zero")

    relevant = set(relevant_ids)
    if not relevant:
        return 1.0

    return len(set(retrieved_ids[:k]).intersection(relevant)) / len(relevant)


def reciprocal_rank_at_k(retrieved_ids: Sequence[str], relevant_ids: Iterable[str], k: int) -> float:
    """Return the reciprocal rank of the first relevant item in the first k results."""
    if k <= 0:
        raise ValueError("k must be greater than zero")

    relevant = set(relevant_ids)
    for rank, note_id in enumerate(retrieved_ids[:k], start=1):
        if note_id in relevant:
            return 1.0 / rank
    return 0.0


def foreign_result_ids(retrieved_ids: Sequence[str], allowed_ids: Iterable[str]) -> list[str]:
    """Return retrieved IDs outside the evaluation case's permitted user corpus."""
    allowed = set(allowed_ids)
    return [note_id for note_id in retrieved_ids if note_id not in allowed]