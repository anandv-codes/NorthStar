"""pgvector-backed implementation of the domain ``VectorStore`` port.

Replaces the local on-disk Chroma store as the runtime vector index. Chunk and
note embeddings live in Postgres (``note_chunks`` / ``notes.embedding``) and are
matched through the user-scoped ``match_note_chunks`` SQL function so no
per-instance disk state is required (safe across Lambda/API instances).

The RPC callable is injectable so the result-mapping logic can be tested
without a live Supabase client.
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Callable

NOTE_CHUNKS_TABLE = os.getenv("SUPABASE_NOTE_CHUNKS_TABLE", "note_chunks")
NOTES_TABLE = os.getenv("SUPABASE_NOTES_TABLE", "notes")


def _default_rpc() -> Callable[[str, dict[str, Any]], Any]:
    from ..db.supabase_client import supabase

    def call(name: str, params: dict[str, Any]) -> Any:
        return supabase.rpc(name, params).execute()

    return call


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if data is None and isinstance(response, dict):
        data = response.get("data")
    if isinstance(data, list):
        return data
    return []


def _default_supabase():
    from ..db.supabase_client import supabase

    return supabase


class PgVectorStore:
    """Concrete ``VectorStore`` implementation backed by pgvector."""

    def __init__(self, rpc: Callable[[str, dict[str, Any]], Any] | None = None) -> None:
        self._rpc = rpc or _default_rpc()

    def query_related_notes(
        self,
        user_id: str,
        embedding: list[float],
        k: int = 3,
        exclude_note_id: str | None = None,
    ) -> list[dict[str, Any]]:
        response = self._rpc(
            "match_note_chunks",
            {
                "query_embedding": embedding,
                "match_user_id": user_id,
                "match_count": max(1, k * 3),
                "exclude_note_id": exclude_note_id,
            },
        )

        best_by_note: dict[str, dict[str, Any]] = {}
        for row in _rows(response):
            note_id = row.get("note_id")
            if not note_id:
                continue
            distance = row.get("distance")
            current = best_by_note.get(note_id)
            if current is None or (distance is not None and distance < current["distance"]):
                best_by_note[note_id] = {
                    "note_id": note_id,
                    "text": row.get("content"),
                    "summary": row.get("summary"),
                    "distance": distance if distance is not None else float("inf"),
                }

        ranked = sorted(best_by_note.values(), key=lambda note: note["distance"])
        return ranked[:k]


def replace_note_chunks(
    user_id: str,
    note_id: str,
    chunks: list[dict[str, Any]],
    supabase: Any | None = None,
) -> int:
    """Replace a note's chunk embeddings (delete-then-insert, idempotent re-index).

    ``chunks`` items need ``chunk_index``, ``content`` and ``embedding``.
    Returns the number of chunks written.
    """
    client = supabase or _default_supabase()
    client.table(NOTE_CHUNKS_TABLE).delete().eq("user_id", user_id).eq("note_id", note_id).execute()

    if not chunks:
        return 0

    rows = [
        {
            "chunk_id": chunk.get("chunk_id") or str(uuid.uuid4()),
            "user_id": user_id,
            "note_id": note_id,
            "chunk_index": chunk["chunk_index"],
            "content": chunk["content"],
            "embedding": chunk["embedding"],
        }
        for chunk in chunks
    ]
    client.table(NOTE_CHUNKS_TABLE).insert(rows).execute()
    return len(rows)


def upsert_note_embedding(user_id: str, note_id: str, embedding: list[float], supabase: Any | None = None) -> None:
    """Store the note-level aggregate embedding on the note row."""
    client = supabase or _default_supabase()
    client.table(NOTES_TABLE).update({"embedding": embedding}).eq("user_id", user_id).eq(
        "note_id", note_id
    ).execute()
