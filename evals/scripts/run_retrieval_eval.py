from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from backend.app.domain.query_retrieval.strategies.sparse import BM25Index
from evals.retrieval import evaluate_retriever


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES_PATH = WORKSPACE_ROOT / "evals" / "datasets" / "northstar_rag_v0_smoke.jsonl"
DEFAULT_CORPUS_PATH = WORKSPACE_ROOT / "evals" / "datasets" / "northstar_rag_v0_smoke_corpus.jsonl"
DEFAULT_RESULTS_PATH = WORKSPACE_ROOT / "evals" / "results" / "northstar_rag_v0_smoke_bm25.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def git_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=WORKSPACE_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run_bm25_evaluation(cases: list[dict[str, Any]], corpus: list[dict[str, Any]], k: int) -> dict[str, Any]:
    notes_by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for note in corpus:
        notes_by_user[str(note["user_id"])].append(note)

    indexes = {
        user_id: BM25Index.from_notes(notes)
        for user_id, notes in notes_by_user.items()
    }
    def retrieve_candidates(query: str, user_id: str, limit: int) -> list[dict[str, Any]]:
        return indexes[user_id].search(query, limit=limit, k1=1.5, b=0.75)

    case_results, summary = evaluate_retriever(
        cases=cases,
        notes_by_user=notes_by_user,
        retrieve_candidates=retrieve_candidates,
        k=k,
    )
    return {
        "runner": "bm25_smoke",
        "code_revision": git_revision(),
        "configuration": {"k": k, "k1": 1.5, "b": 0.75},
        "case_count": len(case_results),
        "summary": summary,
        "cases": case_results,
    }


def _format_number(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.3f}"


def _format_ids(ids: list[str]) -> str:
    return ", ".join(f"`{note_id}`" for note_id in ids) if ids else "None"


def _format_status(value: bool | None) -> str:
    if value is None:
        return "N/A"
    return "Pass" if value else "Fail"


def _markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _format_configuration(configuration: dict[str, Any]) -> str:
    return ", ".join(f"`{key}={value}`" for key, value in configuration.items())


def format_markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    configuration = report["configuration"]
    lines = [
        "# NorthStar Retrieval Evaluation Result",
        "",
        f"- Runner: `{report['runner']}`",
        f"- Code revision: `{report['code_revision']}`",
        f"- Configuration: {_format_configuration(configuration)}",
        f"- Scenario count: {report['case_count']}",
        "",
        "## Summary",
        "",
        "| Metric | Result |",
        "| --- | ---: |",
        f"| Precision@{configuration['k']} | {summary['precision_at_k']:.3f} |",
        f"| Recall@{configuration['k']} | {summary['recall_at_k']:.3f} |",
        f"| MRR@{configuration['k']} | {summary['mean_reciprocal_rank_at_k']:.3f} |",
        f"| Isolation failures | {summary['isolation_failure_count']} |",
        f"| No-context checks | {summary['no_context_pass_count']}/{summary['no_context_case_count']} |",
        f"| Conflict retrieval checks | {summary['conflict_retrieval_pass_count']}/{summary['conflict_case_count']} |",
        "",
        "## Scenario Results",
        "",
        "| Scenario | Query | Retrieved notes | Relevant notes | Precision | Recall | Reciprocal rank | Isolation | No context | Conflict evidence |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |",
    ]

    for result in report["cases"]:
        lines.append(
            "| {scenario} | {query} | {retrieved} | {relevant} | {precision} | {recall} | {reciprocal_rank} | {isolation} | {no_context} | {conflict} |".format(
                scenario=_markdown_cell(str(result["id"])),
                query=_markdown_cell(str(result["query"])),
                retrieved=_format_ids(result["retrieved_note_ids"]),
                relevant=_format_ids(result["relevant_note_ids"]),
                precision=_format_number(result["precision_at_k"]),
                recall=_format_number(result["recall_at_k"]),
                reciprocal_rank=_format_number(result["reciprocal_rank_at_k"]),
                isolation=_format_status(result["isolation_passed"]),
                no_context=_format_status(result["no_context_passed"]),
                conflict=_format_status(result["conflict_retrieval_complete"]),
            )
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This is a deterministic BM25 smoke baseline over synthetic notes. It measures retrieval only; it does not evaluate generated answers, claim support, conflict resolution wording, latency, or model cost.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the NorthStar synthetic BM25 retrieval smoke evaluation.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULTS_PATH)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    if args.k <= 0:
        parser.error("--k must be greater than zero")

    report = run_bm25_evaluation(load_jsonl(args.cases), load_jsonl(args.corpus), args.k)
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