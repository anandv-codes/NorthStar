"""Build scored recall candidates from a completed extraction.

Pure: takes the raw extraction dict plus lightweight context (related note ids,
entity mention counts) and returns candidate rows ready for the repository.
Eligibility is score-based; there are intentionally no per-note/weekly caps
(product decision: the review queue itself limits load).
"""
from __future__ import annotations

from typing import Any

from ..memory.extraction_v2 import item_durability, item_importance
from .candidate_scoring import (
    ELIGIBLE,
    REJECTED,
    ScoringConfig,
    is_eligible,
    load_scoring_config,
    score_candidate,
)
from .text_utils import dedupe_key

# item type -> (text field, id field produced by the typed-table insert)
ITEM_SPECS: dict[str, tuple[str, str]] = {
    "task": ("description", "task_id"),
    "fact": ("content", "fact_id"),
    "concept": ("concept", "concept_id"),
    "question": ("question", "question_id"),
    "decision": ("decision", "decision_id"),
}


def build_candidates(
    extraction: dict[str, Any],
    *,
    source_note_id: str,
    related_note_ids: list[str] | None = None,
    entity_mention_counts: dict[str, int] | None = None,
    note_age_days: float = 0.0,
    user_interest_score: float = 0.0,
    config: ScoringConfig | None = None,
    include_rejected: bool = False,
) -> list[dict[str, Any]]:
    """Return candidates sorted by descending score."""
    config = config or load_scoring_config()
    entity_mention_counts = {k.lower(): v for k, v in (entity_mention_counts or {}).items()}
    related_ids: list[str] = []
    for note_id in related_note_ids or []:
        if note_id and note_id != source_note_id and note_id not in related_ids:
            related_ids.append(note_id)
    related_note_count = len(related_ids) + 1

    candidates: list[dict[str, Any]] = []
    for item_type, (text_field, _id_field) in ITEM_SPECS.items():
        for item in extraction.get(item_type + "s", []) or []:
            text = str(item.get(text_field) or "").strip()
            if not text:
                continue

            importance = item_importance(item)
            mention_count = _mention_count(item, entity_mention_counts)
            score = score_candidate(
                importance=importance,
                mention_count=mention_count,
                related_note_count=related_note_count,
                age_days=note_age_days,
                user_interest_score=user_interest_score,
                config=config,
            )
            eligible = is_eligible(confidence=item.get("confidence"), score=score, config=config)

            candidates.append(
                {
                    "item_type": item_type,
                    "text": text,
                    "source_note_id": source_note_id,
                    "importance": importance,
                    "durability": item_durability(item),
                    "confidence": item.get("confidence"),
                    "mention_count": mention_count,
                    "related_note_count": related_note_count,
                    "recency_score": None,
                    "user_interest_score": user_interest_score,
                    "score": score,
                    "status": ELIGIBLE if eligible else REJECTED,
                    "dedupe_key": dedupe_key(item_type, text),
                    "rationale": {
                        "score": score,
                        "importance": importance,
                        "mention_count": mention_count,
                        "related_note_count": related_note_count,
                        "related_note_ids": related_ids,
                    },
                }
            )

    candidates.sort(key=lambda candidate: candidate["score"], reverse=True)

    if config.max_items_per_note and config.max_items_per_note > 0:
        candidates = candidates[: config.max_items_per_note]

    if include_rejected:
        return candidates
    return [candidate for candidate in candidates if candidate["status"] == ELIGIBLE]


def attach_item_ids(
    candidates: list[dict[str, Any]],
    typed_rows: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Link candidates to their persisted typed-row ids by matching text.

    ``typed_rows`` maps item type -> inserted rows (which include ``<type>_id``).
    Candidates whose text cannot be matched keep ``item_id=None``.
    """
    lookup: dict[tuple[str, str], str] = {}
    for item_type, (_text_field, id_field) in ITEM_SPECS.items():
        for row in typed_rows.get(item_type, []) or []:
            text = (
                row.get("description")
                or row.get("content")
                or row.get("concept")
                or row.get("question")
                or row.get("decision")
                or ""
            )
            item_id = row.get(id_field)
            if text and item_id:
                lookup[(item_type, dedupe_key(item_type, str(text)))] = item_id

    for candidate in candidates:
        candidate["item_id"] = lookup.get((candidate["item_type"], candidate["dedupe_key"]))
    return candidates


def _mention_count(item: dict[str, Any], entity_mention_counts: dict[str, int]) -> int:
    names = [str(name).strip().lower() for name in item.get("entities", []) or [] if str(name).strip()]
    if not names:
        return 1
    return max([entity_mention_counts.get(name, 1) for name in names] + [1])
