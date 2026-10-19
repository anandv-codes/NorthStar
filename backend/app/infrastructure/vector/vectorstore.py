from typing import Any


def _default_embedding_provider() -> Any:
    from .embeddings import get_embeddings

    return get_embeddings()


_DEFAULT_VECTOR_STORE = None


def get_vector_store():
    """Return the process-wide pgvector-backed ``VectorStore``."""
    global _DEFAULT_VECTOR_STORE
    if _DEFAULT_VECTOR_STORE is None:
        from .pg_vector_store import PgVectorStore

        _DEFAULT_VECTOR_STORE = PgVectorStore()
    return _DEFAULT_VECTOR_STORE


def index_note(
    user_id: str,
    note_id: str,
    text: str,
    embedding_provider: Any | None = None,
) -> int:
    """Chunk + embed ``text`` and write the vectors to pgvector.

    Returns the number of chunks indexed.
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
    return len(chunks)
