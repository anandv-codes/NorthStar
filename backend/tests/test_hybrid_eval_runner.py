"""Tests for the offline hybrid evaluation runner's dataset and depth handling."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from evals.scripts.run_hybrid_retrieval_eval import (
    DEFAULT_CASES_PATH,
    HybridRetriever,
    _collection_name,
    _default_output_path,
    _retry_call,
)


V4_CASES = Path("evals/datasets/northstar_rag_v4.jsonl")


def _candidates(count: int) -> list[dict[str, Any]]:
    return [
        {"note_id": f"note-{index}", "text": f"note text {index}"}
        for index in range(count)
    ]


class FakeSparseIndex:
    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results
        self.calls: list[dict[str, Any]] = []

    def search(self, query: str, limit: int, k1: float, b: float) -> list[dict[str, Any]]:
        self.calls.append({"query": query, "limit": limit, "k1": k1, "b": b})
        return self.results[:limit]


class FakeCollection:
    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results
        self.calls: list[dict[str, Any]] = []

    def query(
        self,
        query_embeddings: list[list[float]],
        n_results: int,
        where: dict[str, Any],
        include: list[str],
    ) -> dict[str, Any]:
        self.calls.append({"n_results": n_results, "where": where, "include": include})
        selected = self.results[:n_results]
        return {
            "metadatas": [[{"note_id": item["note_id"], "user_id": where["user_id"]} for item in selected]],
            "documents": [[item["text"] for item in selected]],
            "distances": [[float(index) for index, _ in enumerate(selected)]],
        }


class FakeEmbeddings:
    def embed_query(self, text: str) -> list[float]:
        return [float(len(text))]


class ScoredReranker:
    def rerank(self, query: str, candidates: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
        return [dict(candidate, rerank_score=0.0, score=0.0) for candidate in candidates[:limit]]


class SilentFallbackReranker:
    """Mimics the production reranker's unranked fallback on scoring failure."""

    def rerank(self, query: str, candidates: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
        return candidates[:limit]


def _retriever(
    candidate_limit: int | None,
    reranker: Any = None,
    strict_rerank: bool = False,
) -> tuple[HybridRetriever, FakeSparseIndex, FakeCollection]:
    sparse = FakeSparseIndex(_candidates(15))
    collection = FakeCollection(_candidates(15))
    retriever = HybridRetriever(
        sparse_indexes={"user-1": sparse},
        collection=collection,
        embeddings=FakeEmbeddings(),
        reranker=reranker,
        candidate_limit=candidate_limit,
        strict_rerank=strict_rerank,
    )
    return retriever, sparse, collection


def test_defaults_are_derived_from_the_cases_file():
    assert _default_output_path(V4_CASES, "rrf").name == "northstar_rag_v4_rrf.json"
    assert _collection_name(V4_CASES, "rrf") == "northstar_rag_v4_rrf_eval"
    assert _collection_name(V4_CASES, "rerank") == "northstar_rag_v4_rerank_eval"

    # Unchanged V1 defaults keep the historical artifact and collection names.
    assert _default_output_path(DEFAULT_CASES_PATH, "rerank").name == "northstar_rag_v1_rerank.json"
    assert _collection_name(DEFAULT_CASES_PATH, "rerank") == "northstar_rag_v1_rerank_eval"


def test_candidate_depth_widens_channels_but_limits_final_results():
    retriever, sparse, collection = _retriever(candidate_limit=15)

    results = retriever.retrieve("query", "user-1", limit=5)

    assert sparse.calls[0]["limit"] == 15
    assert collection.calls[0]["n_results"] == 15
    assert len(results) == 5


def test_depth_never_drops_below_the_requested_limit():
    retriever, sparse, collection = _retriever(candidate_limit=3)

    results = retriever.retrieve("query", "user-1", limit=5)

    assert sparse.calls[0]["limit"] == 5
    assert collection.calls[0]["n_results"] == 5
    assert len(results) == 5


def test_strict_rerank_rejects_unscored_candidates():
    retriever, _, _ = _retriever(
        candidate_limit=15,
        reranker=SilentFallbackReranker(),
        strict_rerank=True,
    )

    with pytest.raises(RuntimeError, match="unscored candidates"):
        retriever.retrieve("query", "user-1", limit=5)


def test_scored_reranker_results_pass_the_strict_check():
    retriever, _, _ = _retriever(
        candidate_limit=15,
        reranker=ScoredReranker(),
        strict_rerank=True,
    )

    results = retriever.retrieve("query", "user-1", limit=5)

    assert len(results) == 5
    assert all(result["rerank_score"] is not None for result in results)


def test_retry_call_backs_off_on_rate_limits(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("evals.scripts.run_hybrid_retrieval_eval.time.sleep", sleeps.append)
    attempts = {"count": 0}

    def flaky() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")
        return "ok"

    assert _retry_call(flaky) == "ok"
    assert attempts["count"] == 3
    assert sleeps == [2.0, 4.0]


def test_retry_call_does_not_swallow_non_rate_errors(monkeypatch):
    monkeypatch.setattr("evals.scripts.run_hybrid_retrieval_eval.time.sleep", lambda _: None)

    def broken() -> str:
        raise ValueError("bad request payload")

    with pytest.raises(ValueError, match="bad request"):
        _retry_call(broken)
