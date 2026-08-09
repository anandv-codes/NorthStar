from abc import ABC, abstractmethod
from typing import Any, List

class BaseRetrieval(ABC):
    @abstractmethod
    def retrieve(self, query: str, user_id: str, limit: int = 5) -> List[dict[str, Any]]:
        """Retrieve related notes/documents for a query and user."""
        pass
