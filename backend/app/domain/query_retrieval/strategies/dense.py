from typing import Any, List

from ....infrastructure.vector.embeddings import get_embeddings
from ....infrastructure.vector.vectorstore import query_related_notes
from .base import BaseRetrieval


class DenseRetriever(BaseRetrieval):
    def retrieve(self, query: str, user_id: str, limit: int = 5) -> List[dict[str, Any]]:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return []

        # Get embeddings and query the persistent vector store
        embedding = get_embeddings().embed_query(normalized_query)
        return query_related_notes(
            user_id=user_id,
            embedding=embedding,
            k=limit,
        )
