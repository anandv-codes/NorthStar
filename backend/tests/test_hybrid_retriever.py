"""Tests for the unified hybrid retrieval engine and task-facing policies."""
from __future__ import annotations

from typing import Any

import pytest

from backend.app.domain.query_retrieval.contracts import RetrievalRequest
from backend.app.domain.query_retrieval.hybrid_retriever import (
    HybridRetriever,
    apply_reranking,
    fuse_candidates,
)
from backend.app.domain.query_retrieval.strategies.base import BaseRetrieval
from backend.app.domain.query_retrieval.utils import contains_identifier, extract_identifiers


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return [float(len(text))]


class FakeVectorStore:
    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results
        self.calls: list[dict[str, Any]] = []

    def query_related_notes(
        self,
        user_id: str,
        embedding: list[float],
        k: int = 3,
        exclude_note_id: str | None = None,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            {
                "user_id": user_id,
                "embedding": embedding,
                "k": k,
                "exclude_note_id": exclude_note_id,
            }
        )
        return self.results[:k]


class FakeSparseRetriever(BaseRetrieval):
    def __init__(
        self,
        results: list[dict[str, Any]] | None = None,
        exact_results: list[dict[str, Any]] | None = None,
    ) -> None:
        self.results = results or []
        self.exact_results = exact_results or []
        self.calls: list[dict[str, Any]] = []
        self.exact_calls: list[dict[str, Any]] = []

    def retrieve(
        self,
        query: str,
        user_id: str,
        limit: int = 5,
        exclude_note_id: str | None = None,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            {
                "query": query,
                "user_id": user_id,
                "limit": limit,
                "exclude_note_id": exclude_note_id,
            }
        )
        return self.results[:limit]

    def retrieve_exact_identifiers(
        self,
        query: str,
        user_id: str,
        limit: int = 5,
        exclude_note_id: str | None = None,
    ) -> list[dict[str, Any]]:
        self.exact_calls.append(
            {
                "query": query,
                "user_id": user_id,
                "limit": limit,
                "exclude_note_id": exclude_note_id,
            }
        )
        return self.exact_results[:limit]


class FailingReranker:
    def rerank(self, query: str, candidates: list[dict[str, Any]], limit: int = 5):
        raise AssertionError("reranker should not be called")


def _results(prefix: str, count: int) -> list[dict[str, Any]]:
    return [
        {
            "note_id": f"{prefix}-{index}",
            "text": f"{prefix} text {index}",
            "summary": None,
            "distance": index / 10,
        }
        for index in range(count)
    ]


def _retriever(
    sparse: FakeSparseRetriever,
    vector: FakeVectorStore,
    reranker: Any = None,
) -> HybridRetriever:
    return HybridRetriever(
        embedding_provider=FakeEmbeddingProvider(),
        vector_store=vector,
        sparse_retriever=sparse,
        reranker=reranker,
    )


def test_candidate_depth_is_expanded_before_fusion_and_exclusion_is_pushed_down():
    sparse = FakeSparseRetriever(_results("sparse", 8))
    vector = FakeVectorStore(_results("dense", 8))
    retriever = _retriever(sparse, vector)

    result = retriever.retrieve(
        RetrievalRequest(
            user_id="user-1",
            query="deadlock detection",
            limit=5,
            exclude_note_id="note-self",
        )
    )

    assert vector.calls[0]["k"] == 15
    assert vector.calls[0]["exclude_note_id"] == "note-self"
    assert sparse.calls[0]["limit"] == 15
    assert sparse.calls[0]["exclude_note_id"] == "note-self"
    assert len(result.candidates) == 5
    assert result.source_counts == {
        "exact": 0,
        "sparse": 8,
        "dense_original": 8,
        "dense_rewritten": 0,
    }


def test_exact_identifier_channel_ranks_the_identified_note_first():
    sparse = FakeSparseRetriever(
        _results("sparse", 5),
        exact_results=[
            {"note_id": "item-note", "text": "ITEM-4101 owner Priya", "distance": 0.0}
        ],
    )
    vector = FakeVectorStore(_results("dense", 5))
    retriever = _retriever(sparse, vector)

    result = retriever.retrieve(
        RetrievalRequest(user_id="user-1", query="Who owns ITEM-4101?", limit=5)
    )

    assert result.exact_identifiers == ["item-4101"]
    assert result.candidates[0]["note_id"] == "item-note"
    assert result.candidates[0]["exact_rank"] == 1
    assert sparse.exact_calls[0]["limit"] == 15


def test_rerank_can_be_disabled_and_final_limit_is_still_enforced():
    sparse = FakeSparseRetriever(_results("sparse", 8))
    vector = FakeVectorStore(_results("dense", 8))
    retriever = _retriever(sparse, vector, reranker=FailingReranker())

    result = retriever.retrieve(
        RetrievalRequest(user_id="user-1", query="rrf", limit=5, rerank=False)
    )

    assert len(result.candidates) == 5


def test_apply_reranking_without_reranker_still_truncates():
    candidates = _results("candidate", 8)
    assert len(apply_reranking("q", candidates, None, limit=3)) == 3


def test_fuse_candidates_applies_source_weights():
    fused = fuse_candidates(
        [
            ("exact", [{"note_id": "exact", "text": "exact"}]),
            ("sparse", [{"note_id": "sparse", "text": "sparse"}]),
            ("original", [{"note_id": "dense", "text": "dense"}]),
        ],
        limit=3,
        weights={"exact": 3.0},
    )
    assert [item["note_id"] for item in fused] == ["exact", "sparse", "dense"]


def test_exact_match_wins_a_weight_tie_with_all_generic_channels():
    fused = fuse_candidates(
        [
            ("exact", [{"note_id": "exact", "text": "exact"}]),
            ("sparse", [{"note_id": "generic", "text": "generic"}]),
            ("original", [{"note_id": "generic", "text": "generic"}]),
            ("rewritten", [{"note_id": "generic", "text": "generic"}]),
        ],
        limit=2,
        weights={"exact": 3.0},
    )
    assert [item["note_id"] for item in fused] == ["exact", "generic"]


def test_extract_identifiers_is_specific():
    assert extract_identifiers("Who owns ITEM-4101?") == ["item-4101"]
    assert extract_identifiers("Status of CVE-2026-1234") == ["cve-2026-1234"]
    assert extract_identifiers("deadlock detection") == []
    assert extract_identifiers("meeting on 2026-09-10") == []
    assert contains_identifier("ITEM-4101 is owned by Priya", "item-4101")
    assert not contains_identifier("ITEM-41010 is different", "item-4101")


def test_bm25_exact_search_respects_exclusion():
    pytest.importorskip("rank_bm25")
    from backend.app.domain.query_retrieval.strategies.sparse import BM25Index

    index = BM25Index.from_notes(
        [
            {"note_id": "n1", "raw_text": "ITEM-4101 owner Priya"},
            {"note_id": "n2", "raw_text": "ITEM-4101 owner Marco"},
        ]
    )
    results = index.search_identifiers(["item-4101"], limit=5, exclude_note_id="n1")
    assert [item["note_id"] for item in results] == ["n2"]


def test_exact_query_skips_chat_rewrite(monkeypatch):
    from backend.app.domain.query_retrieval import services

    class Rewriter:
        def __init__(self):
            self.calls = 0

        def rewrite(self, user_query, recent_memory=None):
            self.calls += 1
            raise AssertionError("explicit identifiers must not be rewritten")

    class FakeHybrid:
        def __init__(self):
            self.requests = []

        def retrieve(self, request):
            self.requests.append(request)
            from backend.app.domain.query_retrieval.contracts import RetrievalResult

            return RetrievalResult(request=request, candidates=[])

    rewriter = Rewriter()
    hybrid = FakeHybrid()
    import sys
    from types import SimpleNamespace

    monkeypatch.setitem(
        sys.modules,
        "backend.app.domain.memory.services",
        SimpleNamespace(query_recent_memory_for_user=lambda **kwargs: {}),
    )
    monkeypatch.setattr(services, "get_hybrid_retriever", lambda: hybrid)

    response = services.retrieve_query_context(
        "user-1", "Who owns ITEM-4101?", query_rewriter=rewriter
    )

    assert rewriter.calls == 0
    assert response["fallback_reason"] == "explicit_identifier"
    assert response["explicit_identifiers"] == ["item-4101"]
    assert hybrid.requests[0].mode == "chat"
