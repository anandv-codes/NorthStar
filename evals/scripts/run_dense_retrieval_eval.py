from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from evals.retrieval import evaluate_retriever
from evals.scripts.run_retrieval_eval import (
    WORKSPACE_ROOT,
    format_markdown_report,
    git_revision,
    load_jsonl,
)


DEFAULT_CASES_PATH = WORKSPACE_ROOT / "evals" / "datasets" / "northstar_rag_v1.jsonl"
DEFAULT_CORPUS_PATH = WORKSPACE_ROOT / "evals" / "datasets" / "northstar_rag_v1_corpus.jsonl"
DEFAULT_RESULTS_PATH = WORKSPACE_ROOT / "evals" / "results" / "northstar_rag_v1_dense.json"
DEFAULT_CHROMA_PATH = WORKSPACE_ROOT / "evals" / ".chroma"
DEFAULT_COLLECTION = "northstar_rag_v1_dense_eval"
PRODUCTION_CHROMA_PATH = (WORKSPACE_ROOT / "chroma_data").resolve()
PRODUCTION_COLLECTION = "notes"


class DenseEvaluationPrerequisiteError(RuntimeError):
    """Raised when the local environment cannot execute the dense baseline."""


def _load_dense_dependencies() -> tuple[Any, Any, str]:
    try:
        import chromadb
    except ImportError as error:
        raise DenseEvaluationPrerequisiteError(
            "chromadb is required for the dense evaluation. Install backend requirements first."
        ) from error

    try:
        from backend.app.infrastructure.vector.embeddings import (
            get_embedding_model_id,
            get_embeddings,
        )
    except ImportError as error:
        raise DenseEvaluationPrerequisiteError(
            "langchain-google-genai is required for the dense evaluation. "
            "Install backend requirements first."
        ) from error

    try:
        embeddings = get_embeddings()
    except RuntimeError as error:
        raise DenseEvaluationPrerequisiteError(str(error)) from error

    return chromadb, embeddings, get_embedding_model_id()


def _validate_isolated_target(chroma_path: Path, collection_name: str) -> None:
    if chroma_path.resolve() == PRODUCTION_CHROMA_PATH:
        raise ValueError("The dense evaluation must not use the production chroma_data path.")
    if collection_name == PRODUCTION_COLLECTION:
        raise ValueError("The dense evaluation must not use the production notes collection.")


def run_dense_evaluation(
    cases: list[dict[str, Any]],
    corpus: list[dict[str, Any]],
    k: int,
    chroma_path: Path,
    collection_name: str,
) -> dict[str, Any]:
    _validate_isolated_target(chroma_path, collection_name)
    chromadb, embeddings, embedding_model = _load_dense_dependencies()
    chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_path))

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

    def retrieve_candidates(query: str, user_id: str, limit: int) -> list[dict[str, Any]]:
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

    case_results, summary = evaluate_retriever(
        cases=cases,
        notes_by_user=notes_by_user,
        retrieve_candidates=retrieve_candidates,
        k=k,
    )
    return {
        "runner": "dense_chroma_eval",
        "code_revision": git_revision(),
        "configuration": {
            "k": k,
            "embedding_model": embedding_model,
            "collection": collection_name,
            "storage_path": str(chroma_path.relative_to(WORKSPACE_ROOT)),
        },
        "case_count": len(case_results),
        "summary": summary,
        "cases": case_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run isolated dense Chroma retrieval evaluation over synthetic fixtures."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULTS_PATH)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--chroma-path", type=Path, default=DEFAULT_CHROMA_PATH)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    if args.k <= 0:
        parser.error("--k must be greater than zero")

    try:
        report = run_dense_evaluation(
            cases=load_jsonl(args.cases),
            corpus=load_jsonl(args.corpus),
            k=args.k,
            chroma_path=args.chroma_path,
            collection_name=args.collection,
        )
    except (DenseEvaluationPrerequisiteError, ValueError) as error:
        parser.error(str(error))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_output = args.markdown_output or args.output.with_suffix(".md")
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(format_markdown_report(report), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Wrote report: {args.output}")
    print(f"Wrote Markdown report: {markdown_output}")


if __name__ == "__main__":
    main()