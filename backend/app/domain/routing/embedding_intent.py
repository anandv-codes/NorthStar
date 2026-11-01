from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Iterable, Mapping, Sequence

from .intent_examples import INTENT_EXAMPLES, SemanticIntentLabel


DEFAULT_SEMANTIC_LABELS: tuple[SemanticIntentLabel, ...] = (
    "conversation",
    "note_content",
    "note_status",
)
DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

Embedder = Callable[[Sequence[str]], Sequence[Sequence[float]]]


@dataclass(frozen=True, slots=True)
class SemanticIntentMatch:
    label: SemanticIntentLabel
    confidence: float
    margin: float
    scores: dict[str, float]


class LocalSemanticIntentClassifier:
    """Small in-repo kNN classifier over seed utterances.

    The model and index are loaded lazily so importing the app remains cheap.
    Tests can inject an embedder and avoid downloading model weights.
    """

    def __init__(
        self,
        examples: Mapping[SemanticIntentLabel, Sequence[str]] | None = None,
        model_name: str = DEFAULT_MODEL_NAME,
        embedder: Embedder | None = None,
        labels: Iterable[SemanticIntentLabel] = DEFAULT_SEMANTIC_LABELS,
        threshold: float = 0.42,
        margin: float = 0.03,
        top_examples_per_label: int = 2,
    ) -> None:
        self.examples = examples or INTENT_EXAMPLES
        self.model_name = model_name
        self.embedder = embedder
        self.labels = tuple(labels)
        self.threshold = threshold
        self.margin = margin
        self.top_examples_per_label = max(1, top_examples_per_label)
        self._index: dict[str, list[list[float]]] | None = None

    def classify(self, message: str) -> SemanticIntentMatch | None:
        normalized = " ".join(str(message or "").split()).strip()
        if not normalized:
            return None

        index = self._ensure_index()
        if not index:
            return None

        query_vector = self._normalize(self._embed([normalized])[0])
        if not query_vector:
            return None

        scores: dict[str, float] = {}
        for label, vectors in index.items():
            similarities = sorted(
                (self._dot(query_vector, vector) for vector in vectors),
                reverse=True,
            )
            scores[label] = sum(similarities[: self.top_examples_per_label]) / min(
                self.top_examples_per_label, len(similarities)
            )

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        if not ranked:
            return None
        top_label, top_score = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
        separation = top_score - runner_up
        if top_score < self.threshold or separation < self.margin:
            return None

        return SemanticIntentMatch(
            label=top_label,  # type: ignore[arg-type]
            confidence=round(top_score, 3),
            margin=round(separation, 3),
            scores={label: round(score, 3) for label, score in scores.items()},
        )

    def _ensure_index(self) -> dict[str, list[list[float]]]:
        if self._index is not None:
            return self._index

        texts: list[str] = []
        labels: list[str] = []
        for label in self.labels:
            for text in self.examples.get(label, ()):
                cleaned = " ".join(str(text or "").split()).strip()
                if not cleaned:
                    continue
                texts.append(cleaned)
                labels.append(label)

        if not texts:
            self._index = {}
            return self._index

        vectors = [self._normalize(vector) for vector in self._embed(texts)]
        index: dict[str, list[list[float]]] = {label: [] for label in self.labels}
        for label, vector in zip(labels, vectors):
            if vector:
                index[label].append(vector)
        self._index = index
        return index

    def _embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        if self.embedder is not None:
            return self.embedder(texts)
        model = _load_model(self.model_name)
        encoded = model.encode(
            list(texts),
            normalize_embeddings=False,
            show_progress_bar=False,
        )
        return encoded.tolist() if hasattr(encoded, "tolist") else encoded

    @staticmethod
    def _normalize(vector: Sequence[float]) -> list[float]:
        values = [float(value) for value in vector]
        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0:
            return []
        return [value / norm for value in values]

    @staticmethod
    def _dot(left: Sequence[float], right: Sequence[float]) -> float:
        if len(left) != len(right):
            return 0.0
        return sum(a * b for a, b in zip(left, right))


@lru_cache(maxsize=2)
def _load_model(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


@lru_cache(maxsize=1)
def build_default_semantic_intent_classifier() -> LocalSemanticIntentClassifier:
    return LocalSemanticIntentClassifier()
