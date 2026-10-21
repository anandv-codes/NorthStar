from abc import ABC, abstractmethod
from typing import Any, List


class BaseRetrieval(ABC):
    @abstractmethod
    def retrieve(
        self,
        query: str,
        user_id: str,
        limit: int = 5,
        exclude_note_id: str | None = None,
    ) -> List[dict[str, Any]]:
        """Retrieve related notes/documents for a query and user."""

    def retrieve_exact_identifiers(
        self,
        query: str,
        user_id: str,
        limit: int = 5,
        exclude_note_id: str | None = None,
    ) -> List[dict[str, Any]]:
        """Optional exact-identifier channel; sparse retrieval implements it."""
        return []
