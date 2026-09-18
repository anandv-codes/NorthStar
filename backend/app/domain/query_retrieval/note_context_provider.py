"""Unified context retrieval for note ingestion (Phase A + Phase R).

Combines:
1. Hybrid semantic retrieval (BM25 + dense embeddings + RRF) via NoteContextRetriever
2. Deterministic entity-linked retrieval via EntityContextRetriever

Deduplicates and merges results by note_id. KISS principle: minimal logic, just merge.
"""
from __future__ import annotations

import logging
from typing import Any

from .hybrid_retriever import get_note_context_retriever
from .entity_context_retriever import get_entity_context_retriever

logger = logging.getLogger(__name__)


def fetch_note_context(
    user_id: str,
    raw_text: str,
    limit_hybrid: int = 3,
    exclude_note_id: str | None = None,
) -> dict[str, Any]:
    """
    Fetch context for a note being processed via BOTH semantic AND entity-linked retrieval.
    
    Args:
        user_id: User identifier.
        raw_text: New note's raw text.
        limit_hybrid: Max results from hybrid retrieval (BM25 + dense + RRF).
        exclude_note_id: Note ID to exclude (the note being processed).
    
    Returns:
        Dict with keys:
          - related_notes: list[dict] — merged, deduplicated by note_id
          - matched_entity_names: list[str] — entity names found in raw_text
          - memory_items: list[dict] — structured items linked to matched entities
          - retrieval_sources: dict — metadata (counts from each retriever)
    """
    # Fetch via hybrid retrieval (semantic + sparse + RRF).
    try:
        hybrid_results = get_note_context_retriever().fetch_related_context(
            user_id=user_id,
            raw_text=raw_text,
            limit=limit_hybrid,
            exclude_note_id=exclude_note_id,
        )
    except Exception as exc:
        logger.warning(f"Hybrid retrieval failed; continuing without semantic results: {exc}")
        hybrid_results = []

    # Fetch via entity-linked retrieval (deterministic entity matching).
    try:
        entity_context = get_entity_context_retriever().fetch_related_context_by_entities(
            user_id=user_id,
            raw_text=raw_text,
            exclude_note_id=exclude_note_id,
        )
    except Exception as exc:
        logger.warning(f"Entity context retrieval failed; continuing without entity-linked results: {exc}")
        entity_context = {
            "matched_entity_names": [],
            "related_notes": [],
            "memory_items": [],
        }

    # Merge related notes: deduplicate by note_id, keep semantic scores from hybrid if present.
    merged_notes: dict[str, dict[str, Any]] = {}
    
    # Add hybrid results first (they have ranking/scoring).
    for note in hybrid_results:
        note_id = note.get("note_id")
        if note_id:
            merged_notes[note_id] = note

    # Add entity-linked notes (deduplicate, but don't overwrite hybrid scores).
    for note in entity_context.get("related_notes", []):
        note_id = note.get("note_id")
        if note_id and note_id not in merged_notes:
            # Entity-linked notes don't have retrieval scores; just add raw data.
            merged_notes[note_id] = note

    # Sort merged notes by recency (created_at descending).
    related_notes_list = sorted(
        merged_notes.values(),
        key=lambda n: n.get("created_at") or "",
        reverse=True,
    )

    return {
        "related_notes": related_notes_list,
        "matched_entity_names": entity_context.get("matched_entity_names", []),
        "memory_items": entity_context.get("memory_items", []),
        "retrieval_sources": {
            "hybrid_count": len(hybrid_results),
            "entity_linked_count": len(entity_context.get("related_notes", [])),
            "merged_note_count": len(related_notes_list),
            "memory_items_count": len(entity_context.get("memory_items", [])),
        },
    }
