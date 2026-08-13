import os
from typing import Any


def _normalized_embedding_model_id() -> str:
    return os.getenv("EMBEDDING_MODEL_ID", "gemini-embedding-001").strip()


class LocalSentenceTransformerWrapper:
    """Light wrapper to provide `embed_documents` and `embed_query`.

    Uses `sentence-transformers` (install via `pip install sentence-transformers`).
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:  # pragma: no cover - import guard
            raise RuntimeError(
                "Install 'sentence-transformers' to use local embeddings: pip install sentence-transformers"
            ) from exc
        self._model = SentenceTransformer(model_name)
        self.model_name = model_name

    def embed_documents(self, docs: list[str]) -> list[list[float]]:
        vecs = self._model.encode(docs, show_progress_bar=False)
        # Ensure list[list[float]]
        return [list(v) for v in vecs]

    def embed_query(self, query: str) -> list[float]:
        vec = self._model.encode([query], show_progress_bar=False)
        return list(vec[0])


def get_embeddings() -> Any:
    """Return an embedding provider implementation.

    Controlled by the `EMBEDDING_PROVIDER` env var:
    - `google` (default): uses Gemini via `langchain_google_genai`.
    - `local`: uses a local `sentence-transformers` model.
    - `openai`: uses OpenAI embeddings via `langchain` if available.

    The returned object exposes `embed_documents(list[str])` and
    `embed_query(str)` to match existing consumers.
    """
    provider = os.getenv("EMBEDDING_PROVIDER", "google").strip().lower()
    model_name = _normalized_embedding_model_id()

    if provider == "local":
        # Default to a compact, fast local model when not explicitly provided
        if not model_name or model_name == "gemini-embedding-001":
            model_name = os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        return LocalSentenceTransformerWrapper(model_name)

    if provider == "openai":
        try:
            # Lazy import to avoid forcing extra deps for users who don't use OpenAI
            from langchain.embeddings import OpenAIEmbeddings
        except Exception as exc:  # pragma: no cover - import guard
            raise RuntimeError(
                "Install 'langchain' (and openai) to use OpenAI embeddings: pip install langchain openai"
            ) from exc
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY must be set to use OpenAI embeddings")
        # OpenAI's small embedding models are typically specified via EMBEDDING_MODEL_ID
        return OpenAIEmbeddings(model=model_name, openai_api_key=api_key)

    # Default: Google Gemini embeddings (existing behavior)
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "Install 'langchain-google-genai' to use Gemini embeddings: pip install langchain-google-genai"
        ) from exc
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY must be set to use Gemini embeddings")
    # If user explicitly set EMBEDDING_MODEL_ID it will be used; otherwise keep default
    return GoogleGenerativeAIEmbeddings(model=model_name, google_api_key=api_key)


def get_embedding_model_id() -> str:
    return _normalized_embedding_model_id()


def get_embedding_provider() -> Any:
    """Return the default embedding provider object for the domain layer.

    This object implements `embed_documents` and `embed_query` used elsewhere
    in the project.
    """
    return get_embeddings()
