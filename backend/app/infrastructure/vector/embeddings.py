import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings


def _normalized_embedding_model_id() -> str:
    model_id = os.getenv("EMBEDDING_MODEL_ID", "gemini-embedding-001").strip()
    
    return model_id


def get_embeddings():
    """Return the embedding model used by the local RAG pipeline."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY must be set to use embeddings")
    model_name=_normalized_embedding_model_id()
    return GoogleGenerativeAIEmbeddings(
        model=model_name,
        google_api_key=api_key,
    )


def get_embedding_model_id() -> str:
    return _normalized_embedding_model_id()


def get_embedding_provider():
    """Return the default ``EmbeddingProvider`` implementation.

    The returned object already satisfies the domain ``EmbeddingProvider``
    protocol (it exposes ``embed_query``), so no separate adapter class is
    required.
    """
    return get_embeddings()
