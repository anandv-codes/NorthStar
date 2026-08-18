from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from backend.app.domain.query_retrieval.strategies.sparse import BM25Index
from evals.retrieval import evaluate_retriever
from evals.scripts.run_dense_retrieval_eval import (
    DEFAULT_CHROMA_PATH,
    DenseEvaluationPrerequisiteError,
    _load_dense_dependencies,
    _validate_isolated_target,
)
from evals.scripts.run_retrieval_eval import (
    WORKSPACE_ROOT,
    format_markdown_report,
    git_revision,
    load_jsonl,
)


DEFAULT_CASES_PATH = WORKSPACE_ROOT / "evals" / "datasets" / "northstar_rag_v1.jsonl"
DEFAULT_CORPUS_PATH = WORKSPACE_ROOT / "evals" / "datasets" / "northstar_rag_v1_corpus.jsonl"
DEFAULT_REWRITE_CACHE_PATH = WORKSPACE_ROOT / "evals" / "cache" / "northstar_rag_v1_rewrites.json"


def _default_output_path(mode: str) -> Path:
    return WORKSPACE_ROOT / "evals" / "results" / f"northstar_rag_v1_{mode}.json"


def _collection_name(mode: str) -> str:
    return f"northstar_rag_v1_{mode}_eval"


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path)


def _load_rewrite_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}

    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw.get("entries", raw) if isinstance(raw, dict) else {}
    if not isinstance(entries, dict):
        return {}

    return {
        str(query): value
        for query, value in entries.items()
        if isinstance(value, dict)
    }


def _write_rewrite_cache(path: Path, entries: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "description": "Cached raw Gemini query rewrite results for hybrid retrieval evals.",
        "entries": entries,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_cached_rewriter(
    rewrite_query_with_llm: Any,
    cache_path: Path,
    latency_seconds: float = 0.0,
    refresh_cache: bool = False,
) -> tuple[Any, dict[str, int]]:
    cache = _load_rewrite_cache(cache_path)
    stats = {"hits": 0, "misses": 0, "refreshes": 0}
    last_request_at: float | None = None

    def cached_rewrite_query_with_llm(user_query: str, recent_memory: dict[str, Any] | None = None) -> dict[str, Any]:
        nonlocal last_request_at
        cache_key = str(user_query)
        if cache_key in cache and not refresh_cache:
            stats["hits"] += 1
            return dict(cache[cache_key])

        stats["misses"] += 1
        if cache_key in cache and refresh_cache:
            stats["refreshes"] += 1
        if latency_seconds > 0 and last_request_at is not None:
            elapsed = time.monotonic() - last_request_at
            if elapsed < latency_seconds:
                time.sleep(latency_seconds - elapsed)

        last_request_at = time.monotonic()
        rewrite_result = rewrite_query_with_llm(user_query=user_query, recent_memory=recent_memory)
        cache[cache_key] = dict(rewrite_result)
        _write_rewrite_cache(cache_path, cache)
        return rewrite_result

    return cached_rewrite_query_with_llm, stats


def _guarded_rewrite_query(query: str, rewrite_query_with_llm: Any, rewrite_tools: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    query_quality = rewrite_tools["score_query_quality"](query)
    audit: dict[str, Any] = {
        "query_quality": query_quality,
        "rewrite_used": False,
        "rewritten_query": None,
        "likely_answer": None,
        "rewrite_confidence": None,
        "risk_flags": [],
        "fallback_reason": None,
    }
    if query_quality < rewrite_tools["min_query_quality"]:
        audit["fallback_reason"] = "low_query_quality"
        return query, audit

    rewrite_result = rewrite_query_with_llm(user_query=query, recent_memory={})
    rewritten_query = str(rewrite_result.get("rewritten_query") or query).strip()
    likely_answer = str(rewrite_result.get("likely_answer") or "").strip()
    confidence = float(rewrite_result.get("confidence") or 0.0)
    risk_flags = rewrite_tools["detect_rewrite_risks"](
        original_query=query,
        rewritten_query=rewritten_query,
        likely_answer=likely_answer,
        llm_flags=rewrite_result.get("risk_flags") or [],
    )
    audit.update(
        {
            "rewritten_query": rewritten_query,
            "likely_answer": likely_answer,
            "rewrite_confidence": confidence,
            "risk_flags": risk_flags,
        }
    )
    if confidence < rewrite_tools["min_rewrite_confidence"] or risk_flags:
        audit["fallback_reason"] = "rewrite_confidence_or_risk_threshold"
        return query, audit

    audit["rewrite_used"] = True
    expanded_query = " ".join(part for part in [query, rewritten_query, likely_answer] if part).strip()
    return expanded_query, audit


def _query_dense_notes(
    collection: Any,
    embeddings: Any,
    query: str,
    user_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    result = collection.query(
        query_embeddings=[embeddings.embed_query(query)],
        n_results=limit,
        where={"user_id": user_id},
        include=["metadatas", "documents", "distances"],
    )
    metadatas = (result.get("metadatas") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    return [
        {
            "note_id": metadata.get("note_id"),
            "text": document,
            "distance": distance,
        }
        for metadata, document, distance in zip(metadatas, documents, distances)
        if metadata and metadata.get("note_id")
    ]


def run_hybrid_evaluation(
    cases: list[dict[str, Any]],
    corpus: list[dict[str, Any]],
    mode: str,
    k: int,
    chroma_path: Path,
    rewrite_cache_path: Path | None = None,
    rewrite_latency_seconds: float = 0.0,
    refresh_rewrite_cache: bool = False,
) -> dict[str, Any]:
    _validate_isolated_target(chroma_path, _collection_name(mode))
    chromadb, embeddings, embedding_model = _load_dense_dependencies()

    # These are production retrieval subjects; the fixture data and vector store stay evaluation-only.
    from backend.app.domain.query_retrieval.reranker.heuristic import TokenOverlapReranker
    from backend.app.domain.query_retrieval.services import (
        MIN_QUERY_QUALITY_TO_REWRITE,
        MIN_REWRITE_CONFIDENCE,
        detect_rewrite_risks,
        fuse_candidates,
        score_query_quality,
    )

    rewrite_query_with_llm = None
    rewrite_tools: dict[str, Any] | None = None
    rewrite_audits: dict[str, dict[str, Any]] = {}
    rewrite_cache_stats: dict[str, int] | None = None
    if mode == "rewrite":
        from backend.app.infrastructure.llm.query_rewriter import rewrite_query_with_llm

        if rewrite_cache_path is not None:
            rewrite_query_with_llm, rewrite_cache_stats = _build_cached_rewriter(
                rewrite_query_with_llm,
                rewrite_cache_path,
                latency_seconds=rewrite_latency_seconds,
                refresh_cache=refresh_rewrite_cache,
            )

        rewrite_tools = {
            "score_query_quality": score_query_quality,
            "detect_rewrite_risks": detect_rewrite_risks,
            "min_query_quality": MIN_QUERY_QUALITY_TO_REWRITE,
            "min_rewrite_confidence": MIN_REWRITE_CONFIDENCE,
        }

    chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_path))
    collection_name = _collection_name(mode)
    try:
        client.delete_collection(collection_name)
    except (ValueError, chromadb.errors.NotFoundError):
        pass
    collection = client.get_or_create_collection(collection_name)
    collection.add(
        ids=[f"{note['user_id']}:{note['note_id']}" for note in corpus],
        embeddings=embeddings.embed_documents([str(note["raw_text"]) for note in corpus]),
        metadatas=[
            {
                "user_id": str(note["user_id"]),
                "note_id": str(note["note_id"]),
                "created_at": str(note["created_at"]),
            }
            for note in corpus
        ],
        documents=[str(note["raw_text"]) for note in corpus],
    )

    notes_by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for note in corpus:
        notes_by_user[str(note["user_id"])].append(note)
    sparse_indexes = {
        user_id: BM25Index.from_notes(notes)
        for user_id, notes in notes_by_user.items()
    }
    reranker = TokenOverlapReranker() if mode == "rerank" else None

    def retrieve_candidates(query: str, user_id: str, limit: int) -> list[dict[str, Any]]:
        sparse_results = sparse_indexes[user_id].search(query, limit=limit, k1=1.5, b=0.75)
        dense_results = _query_dense_notes(collection, embeddings, query, user_id, limit)
        rewritten_results: list[dict[str, Any]] = []
        if rewrite_query_with_llm is not None and rewrite_tools is not None:
            expanded_query, rewrite_audit = _guarded_rewrite_query(
                query,
                rewrite_query_with_llm,
                rewrite_tools,
            )
            rewrite_audits[query] = rewrite_audit
            if rewrite_audit["rewrite_used"]:
                rewritten_results = _query_dense_notes(collection, embeddings, expanded_query, user_id, limit)
        candidates = fuse_candidates(
            candidate_lists=[
                ("sparse", sparse_results),
                ("original", dense_results),
                ("rewritten", rewritten_results),
            ],
            limit=limit,
        )
        if reranker is not None:
            return reranker.rerank(query, candidates, limit=limit)
        return candidates

    case_results, summary = evaluate_retriever(
        cases=cases,
        notes_by_user=notes_by_user,
        retrieve_candidates=retrieve_candidates,
        k=k,
    )
    if mode == "rewrite":
        for result in case_results:
            result["rewrite"] = rewrite_audits.get(result["query"])
        summary["rewrite_used_count"] = sum(
            audit["rewrite_used"] for audit in rewrite_audits.values()
        )
        summary["rewrite_case_count"] = len(rewrite_audits)
        if rewrite_cache_stats is not None:
            summary["rewrite_cache_hit_count"] = rewrite_cache_stats["hits"]
            summary["rewrite_cache_miss_count"] = rewrite_cache_stats["misses"]
            summary["rewrite_cache_refresh_count"] = rewrite_cache_stats["refreshes"]
    return {
        "runner": f"hybrid_{mode}_eval",
        "code_revision": git_revision(),
        "configuration": {
            "k": k,
            "mode": mode,
            "embedding_model": embedding_model,
            "collection": collection_name,
            "storage_path": str(chroma_path.relative_to(WORKSPACE_ROOT)),
            "fusion": "production_rrf",
            "reranker": "production_token_overlap" if reranker is not None else "off",
            "rewrite": "production_guarded_rewrite_with_empty_synthetic_memory" if mode == "rewrite" else "off",
            "rewrite_cache": _display_path(rewrite_cache_path) if rewrite_cache_path else "off",
            "rewrite_latency_seconds": rewrite_latency_seconds if mode == "rewrite" else 0.0,
            "refresh_rewrite_cache": bool(refresh_rewrite_cache) if mode == "rewrite" else False,
        },
        "case_count": len(case_results),
        "summary": summary,
        "cases": case_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run isolated RRF, guarded-rewrite, or RRF-plus-reranker evaluation over synthetic fixtures."
    )
    parser.add_argument("--mode", choices=("rrf", "rewrite", "rerank"), required=True)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--chroma-path", type=Path, default=DEFAULT_CHROMA_PATH)
    parser.add_argument(
        "--rewrite-cache",
        type=Path,
        default=DEFAULT_REWRITE_CACHE_PATH,
        help="Cache file for raw LLM rewrite results when --mode rewrite. Use 'off' to disable.",
    )
    parser.add_argument(
        "--latency",
        "--rewrite-latency",
        dest="rewrite_latency",
        type=float,
        default=None,
        help="Minimum seconds between live rewrite requests. Applies only to cache misses.",
    )
    parser.add_argument(
        "--rewrite-requests-per-minute",
        type=float,
        default=10.0,
        help="Live rewrite request cap used when --rewrite-latency is omitted. Default: 10.",
    )
    parser.add_argument(
        "--refresh-rewrite-cache",
        action="store_true",
        help="Ignore cached rewrite entries, call Gemini again, and overwrite cache entries.",
    )
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    if args.k <= 0:
        parser.error("--k must be greater than zero")
    if args.rewrite_latency is not None and args.rewrite_latency < 0:
        parser.error("--rewrite-latency must be greater than or equal to zero")
    if args.rewrite_requests_per_minute <= 0:
        parser.error("--rewrite-requests-per-minute must be greater than zero")

    rewrite_cache_path = None
    if args.mode == "rewrite" and str(args.rewrite_cache).strip().lower() not in {"", "off", "none", "false"}:
        rewrite_cache_path = args.rewrite_cache
    rewrite_latency_seconds = 0.0
    if args.mode == "rewrite":
        rewrite_latency_seconds = (
            args.rewrite_latency
            if args.rewrite_latency is not None
            else 60.0 / args.rewrite_requests_per_minute
        )

    try:
        report = run_hybrid_evaluation(
            cases=load_jsonl(args.cases),
            corpus=load_jsonl(args.corpus),
            mode=args.mode,
            k=args.k,
            chroma_path=args.chroma_path,
            rewrite_cache_path=rewrite_cache_path,
            rewrite_latency_seconds=rewrite_latency_seconds,
            refresh_rewrite_cache=args.refresh_rewrite_cache,
        )
    except (DenseEvaluationPrerequisiteError, ValueError) as error:
        parser.error(str(error))

    output = args.output or _default_output_path(args.mode)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_output = args.markdown_output or output.with_suffix(".md")
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(format_markdown_report(report), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Wrote report: {output}")
    print(f"Wrote Markdown report: {markdown_output}")


if __name__ == "__main__":
    main()
