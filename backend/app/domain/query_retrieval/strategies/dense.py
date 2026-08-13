from typing import Any, List

from ....infrastructure.vector.embeddings import get_embedding_provider
from ....infrastructure.vector.vectorstore import get_vector_store
from ...ports import EmbeddingProvider, VectorStore
from .base import BaseRetrieval


class DenseRetriever(BaseRetrieval):
    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self._embedding_provider = embedding_provider or get_embedding_provider()
        self._vector_store = vector_store or get_vector_store()

    def retrieve(self, query: str, user_id: str, limit: int = 5) -> List[dict[str, Any]]:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return []

        # Get embeddings and query the persistent vector store
        embedding = self._embedding_provider.embed_query(normalized_query)
        return self._vector_store.query_related_notes(
            user_id=user_id,
            embedding=embedding,
            k=limit,
        )

