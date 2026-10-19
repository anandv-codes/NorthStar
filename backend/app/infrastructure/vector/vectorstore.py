import os
from typing import Any


CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_data")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "notes")

_TRUTHY = {"1", "true", "yes", "on"}


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in _TRUTHY


def _default_embedding_provider() -> Any:
    from .embeddings import get_embeddings

    return get_embeddings()


_CHROMA_CLIENT = None
_CHROMA_COLLECTION_CACHE = None


def _collection():
    # Reuse a single persistent client/collection instead of reopening the on-disk DB every call.
    global _CHROMA_CLIENT, _CHROMA_COLLECTION_CACHE
    if _CHROMA_COLLECTION_CACHE is None:
        import chromadb

        _CHROMA_CLIENT = chromadb.PersistentClient(path=CHROMA_PATH)
        _CHROMA_COLLECTION_CACHE = _CHROMA_CLIENT.get_or_create_collection(CHROMA_COLLECTION)
    return _CHROMA_COLLECTION_CACHE


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


_DEFAULT_VECTOR_STORE = None


def get_vector_store():
    """Return the process-wide default ``VectorStore`` implementation.

    ``VECTOR_BACKEND=pgvector`` (default) returns the Postgres/pgvector store;
    set ``VECTOR_BACKEND=chroma`` only for the transition/parity window — Chroma
    must not be the runtime store in production.
    """
    global _DEFAULT_VECTOR_STORE
    if _DEFAULT_VECTOR_STORE is None:
        backend = os.getenv("VECTOR_BACKEND", "pgvector").strip().lower()
        if backend == "chroma":
            _DEFAULT_VECTOR_STORE = ChromaVectorStore()
        else:
            from .pg_vector_store import PgVectorStore

            _DEFAULT_VECTOR_STORE = PgVectorStore()
    return _DEFAULT_VECTOR_STORE


def index_note(
    user_id: str,
    note_id: str,
    text: str,
    summary: str = "",
    embedding_provider: Any | None = None,
) -> int:
    """Chunk + embed ``text`` and write the vectors to the pgvector store.

    Returns the number of chunks indexed. During the migration window,
    ``VECTOR_DUAL_WRITE_CHROMA=true`` additionally writes the note-level
    embedding to the legacy Chroma store so its eval index stays fresh.
    """
    from .chunking import chunk_text
    from .pg_vector_store import replace_note_chunks

    chunks = chunk_text(text)
    if not chunks:
        replace_note_chunks(user_id=user_id, note_id=note_id, chunks=[])
        return 0

    provider = embedding_provider or _default_embedding_provider()
    vectors = provider.embed_documents(chunks)
    replace_note_chunks(
        user_id=user_id,
        note_id=note_id,
        chunks=[
            {"chunk_index": index, "content": content, "embedding": vector}
            for index, (content, vector) in enumerate(zip(chunks, vectors))
        ],
    )

    if _truthy_env("VECTOR_DUAL_WRITE_CHROMA"):
        upsert_note_embedding(
            user_id=user_id,
            note_id=note_id,
            text=text,
            embedding=provider.embed_query(text),
            metadata={"summary": summary},
        )
    return len(chunks)


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
