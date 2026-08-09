from abc import ABC, abstractmethod
from typing import Any, List

class BaseReranker(ABC):
    @abstractmethod
    def rerank(self, query: str, candidates: List[dict[str, Any]], limit: int = 5) -> List[dict[str, Any]]:
        """Rerank candidates based on their relevance to the query."""
        pass
