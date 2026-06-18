import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings


def get_embeddings():
    """Return the embedding model used by the local RAG pipeline."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY must be set to use embeddings")
    return GoogleGenerativeAIEmbeddings(
        model=os.getenv("EMBEDDING_MODEL_ID", "models/text-embedding-004"),
    )
    # TODO: Instantiate GoogleGenerativeAIEmbeddings here.
    # Keep this as a factory so the rest of the app does not care which
    # embedding provider backs the vector search.
    raise NotImplementedError("TODO: create and return the embedding model")


def get_embedding_model_id() -> str:
    return os.getenv("EMBEDDING_MODEL_ID", "models/text-embedding-004")
