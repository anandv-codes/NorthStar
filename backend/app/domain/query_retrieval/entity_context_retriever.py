"""Entity-linked context retrieval for note ingestion.

Deterministic (non-similarity) context gathering via shared entity references.
When processing a new note, identifies known entity names mentioned in the text,
then reverse-looks up OTHER notes and structured items (tasks/facts/etc) linked
to those entities, providing deterministic cross-reference context.

Follows SOLID: DI (repository injected), SRP (entity matching only, no retrieval pipeline).
"""
from __future__ import annotations

import logging
from typing import Any

from ..ports import MemoryRepository
from ...infrastructure.db.memory_repository import get_memory_repository

logger = logging.getLogger(__name__)


def _normalize_entity_name(name: str) -> str:
    """Normalize entity name for case-insensitive substring matching."""
    return str(name or "").strip().lower()


def _find_matched_entity_names(raw_text: str, candidate_entity_names: list[str]) -> list[str]:
    """
    Deterministic substring match: find which entity names appear in raw_text.
    
    Case-insensitive. Returns normalized (lowercase, stripped) matched names.
    """
    if not raw_text or not candidate_entity_names:
        return []
    
    normalized_text = raw_text.lower()
    matched = []
    seen = set()
    
    for entity_name in candidate_entity_names:
        normalized = _normalize_entity_name(entity_name)
        if normalized and normalized not in seen:
            # Word-boundary check: entity name should not be a substring of a larger word
            # (e.g., "4575" should match "4575", not "14575" or "45750")
            # For now: simple contains check (can be enhanced with word-boundary regex if needed)
            if normalized in normalized_text:
                matched.append(normalized)
                seen.add(normalized)
    
    return matched


class EntityContextRetriever:
    """
    Single source for entity-linked context lookup.
    
    No query rewriting, no embedding. Pure deterministic entity name matching +
    reverse lookup via memory_item_entities table links.
    """

    def __init__(self, memory_repository: MemoryRepository | None = None):
        self.memory_repository = memory_repository or get_memory_repository()

    def fetch_related_context_by_entities(
        self,
        user_id: str,
        raw_text: str,
        exclude_note_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Find all notes and structured items related via shared entity references.
        
        Args:
            user_id: User identifier.
            raw_text: Text to scan for entity name matches.
            exclude_note_id: Note ID to exclude from results (the note being processed).
        
        Returns:
            Dict with keys:
              - matched_entity_names: list[str] — entity names found in raw_text
              - related_notes: list[dict] — notes linked to matched entities
              - memory_items: list[dict] — structured items (tasks/facts/etc) linked
        """
        # Fetch all entity names for the user (cacheable).
        try:
            all_entity_names = self.memory_repository.query_entity_names_for_user(user_id)
        except Exception as exc:
            logger.warning(f"Failed to fetch entity names for user {user_id}: {exc}")
            all_entity_names = []

        if not all_entity_names:
            return {
                "matched_entity_names": [],
                "related_notes": [],
                "memory_items": [],
            }

        # Deterministic substring match against raw_text.
        matched_entity_names = _find_matched_entity_names(raw_text, all_entity_names)

        if not matched_entity_names:
            return {
                "matched_entity_names": [],
                "related_notes": [],
                "memory_items": [],
            }

        # Reverse-lookup notes linked to matched entities.
        try:
            related_notes = self.memory_repository.query_source_notes_by_entity_names(
                user_id=user_id,
                entity_names=matched_entity_names,
                exclude_note_id=exclude_note_id,
            )
        except Exception as exc:
            logger.warning(f"Failed to fetch related notes by entity names: {exc}")
            related_notes = []

        # Reverse-lookup structured items linked to matched entities.
        try:
            memory_items = self.memory_repository.query_memory_items_by_entity_names(
                user_id=user_id,
                entity_names=matched_entity_names,
                exclude_note_id=exclude_note_id,
            )
        except Exception as exc:
            logger.warning(f"Failed to fetch memory items by entity names: {exc}")
            memory_items = []

        return {
            "matched_entity_names": matched_entity_names,
            "related_notes": related_notes,
            "memory_items": memory_items,
        }


# Module-level singleton.
_ENTITY_CONTEXT_RETRIEVER_INSTANCE: EntityContextRetriever | None = None


def get_entity_context_retriever() -> EntityContextRetriever:
    """Singleton factory for EntityContextRetriever."""
    global _ENTITY_CONTEXT_RETRIEVER_INSTANCE
    if _ENTITY_CONTEXT_RETRIEVER_INSTANCE is None:
        _ENTITY_CONTEXT_RETRIEVER_INSTANCE = EntityContextRetriever()
    return _ENTITY_CONTEXT_RETRIEVER_INSTANCE
