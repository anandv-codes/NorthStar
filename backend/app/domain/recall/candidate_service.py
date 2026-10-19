"""Persist recall candidates produced from a completed note extraction.

The scoring itself is pure (``candidate_engine``); this service only maps the
result onto the ``RecallRepository`` port and de-duplicates via ``dedupe_key``.
"""
from __future__ import annotations

from typing import Any

from .candidate_engine import attach_item_ids, build_candidates
from .candidate_scoring import ScoringConfig


def generate_candidates(
    user_id: str,
    note_id: str,
    extraction: dict[str, Any],
    *,
    related_note_ids: list[str] | None = None,
    entity_rows: list[dict[str, Any]] | None = None,
    typed_rows: dict[str, list[dict[str, Any]]] | None = None,
    config: ScoringConfig | None = None,
    repo: Any | None = None,
) -> list[dict[str, Any]]:
    """Build, link, and persist eligible candidates.

    Returns only newly created/refreshed (still ``eligible``) candidates.
    Candidates already past scoring (suggested/carded/rejected) are left
    untouched and omitted, so re-processing cannot wipe generated questions.
    """
    if repo is None:
        from ...infrastructure.db.recall_repository import get_recall_repository

        repo = get_recall_repository()

    entity_mention_counts = {
        str(row.get("name", "")).strip().lower(): int(row.get("mention_count") or 1)
        for row in (entity_rows or [])
        if row.get("name")
    }

    candidates = build_candidates(
        extraction,
        source_note_id=note_id,
        related_note_ids=related_note_ids,
        entity_mention_counts=entity_mention_counts,
        config=config,
    )
    attach_item_ids(candidates, typed_rows or {})
    if not candidates:
        return []

    # Idempotency: never clobber a candidate that has moved past scoring.
    # Re-processing a note (SQS retry, manual retry) must not wipe a generated
    # question or resurrect an accepted/rejected/carded candidate.
    existing = {
        row.get("dedupe_key"): row
        for row in repo.query_candidates(
            user_id, limit=1000, source_note_id=note_id
        )
        if row.get("dedupe_key")
    }

    persisted: list[dict[str, Any]] = []
    for candidate in candidates:
        prior = existing.get(candidate["dedupe_key"])
        if prior is not None and prior.get("status") not in ("new", "eligible"):
            continue

        row = {
            "item_type": candidate["item_type"],
            "item_id": candidate.get("item_id"),
            "source_note_id": candidate["source_note_id"],
            "text": candidate["text"],
            "prompt": None,
            "answer": None,
            "importance": candidate["importance"],
            "durability": candidate["durability"],
            "mention_count": candidate["mention_count"],
            "related_note_count": candidate["related_note_count"],
            "recency_score": candidate.get("recency_score"),
            "user_interest_score": candidate.get("user_interest_score"),
            "score": candidate["score"],
            "status": candidate["status"],
            "dedupe_key": candidate["dedupe_key"],
            "rationale": candidate["rationale"],
        }
        if prior is not None and prior.get("created_at"):
            # Preserve the original creation time on refresh.
            row["created_at"] = prior["created_at"]
        persisted.append(repo.upsert_candidate(user_id, row))
    return persisted
