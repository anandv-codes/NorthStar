import os
from typing import Any


CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_data")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "notes")


def _collection():
    import chromadb

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(CHROMA_COLLECTION)


def upsert_note_embedding(
    user_id: str,
    note_id: str,
    text: str,
    embedding: list[float],
    metadata: dict[str, Any] | None = None,
) -> None:
    """Store a note vector under a user-scoped ID."""
    collection = _collection()
    merged_metadata = {"user_id": user_id, "note_id": note_id, **(metadata or {})}

    collection.upsert(
        ids=[f"{user_id}:{note_id}"],
        embeddings=[embedding],
        metadatas=[merged_metadata],
        documents=[text],
    )


class ChromaVectorStore:
    """Concrete ``VectorStore`` implementation backed by Chroma."""

    def query_related_notes(
        self,
        user_id: str,
        embedding: list[float],
        k: int = 3,
        exclude_note_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return query_related_notes(user_id=user_id, embedding=embedding, k=k, exclude_note_id=exclude_note_id)


_DEFAULT_VECTOR_STORE: ChromaVectorStore | None = None


def get_vector_store() -> ChromaVectorStore:
    """Return the process-wide default ``VectorStore`` implementation."""
    global _DEFAULT_VECTOR_STORE
    if _DEFAULT_VECTOR_STORE is None:
        _DEFAULT_VECTOR_STORE = ChromaVectorStore()
    return _DEFAULT_VECTOR_STORE


def query_related_notes(
    user_id: str,
    embedding: list[float],
    k: int = 3,
    exclude_note_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return the top related notes for the same user."""
    collection = _collection()
    result = collection.query(
        query_embeddings=[embedding],
        n_results=k + 1,  # Get one extra in case we need to exclude the same note
        where={"user_id": user_id},
        include=["metadatas", "documents","distances"],
    )

    documents = result.get("documents") or [[]]
    metadatas = result.get("metadatas") or [[]]
    distances = result.get("distances") or [[]]

    notes = []
    for doc, metadata, distance in zip(documents[0], metadatas[0], distances[0]):
        metadata = metadata or {}
        if exclude_note_id and metadata.get("note_id") == exclude_note_id:
            continue

        notes.append(
            {
                "note_id": metadata.get("note_id"),
                "text": doc,
                "summary": metadata.get("summary"),
                "distance": distance,
            }
        )
        if len(notes) >= k:
            break
    return notes
