"""Context retrieval for note ingestion.

Fetches related notes via the hybrid retriever (BM25 + dense + RRF) and
deduplicates them by note_id.

Entity-linked retrieval is intentionally not part of this path. It was removed
because it never produced results (see docs/code-review.md, C4); a future
entity linkage should be designed there rather than bolted onto ingestion.
"""
from __future__ import annotations

import logging
from typing import Any

from .contracts import ContextBundle
from .hybrid_retriever import get_note_context_retriever

logger = logging.getLogger(__name__)


def fetch_note_context(
    user_id: str,
    raw_text: str,
    limit_hybrid: int = 3,
    exclude_note_id: str | None = None,
) -> dict[str, Any]:
    """
    Fetch related notes for a note being processed.

    Args:
        user_id: User identifier.
        raw_text: New note's raw text.
        limit_hybrid: Max results from hybrid retrieval (BM25 + dense + RRF).
        exclude_note_id: Note ID to exclude (the note being processed).

    Returns:
        Dict with keys:
          - related_notes: list[dict] — deduplicated by note_id, newest first
          - retrieval_sources: dict — count metadata from the retriever
    """
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

    # Deduplicate by note_id, keeping the first (best-ranked) occurrence.
    merged_notes: dict[str, dict[str, Any]] = {}
    for note in hybrid_results:
        note_id = note.get("note_id")
        if note_id and note_id not in merged_notes:
            merged_notes[note_id] = note

    # Sort merged notes by recency (created_at descending).
    related_notes_list = sorted(
        merged_notes.values(),
        key=lambda n: n.get("created_at") or "",
        reverse=True,
    )

    bundle = ContextBundle(
        notes=related_notes_list,
        sources={
            "hybrid_count": len(hybrid_results),
            "merged_note_count": len(related_notes_list),
        },
    )
    return bundle.to_dict()
