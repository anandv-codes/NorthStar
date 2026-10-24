"""Deterministic regression evaluation for recall question/answer generation.

The runner replays recorded model responses through the production prompt
builder and validators. It does not claim to measure model quality; it protects
the generation contract: question-form matching, answer grounding, answer
coverage, and the multi-note context that both prompts must receive.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from backend.app.domain.recall.card_generation import (
    RecallConfig,
    generate_question_with_answer,
)
from backend.app.domain.recall.text_utils import normalize_text

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES_PATH = (
    WORKSPACE_ROOT / "evals" / "datasets" / "northstar_recall_generation_v1.jsonl"
)
DEFAULT_RESULTS_PATH = (
    WORKSPACE_ROOT / "evals" / "results" / "northstar_recall_generation_v1.json"
)

QUESTION_FORMS = ("how", "what", "why", "when", "who")


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


class ReplayChatModel:
    """Return one recorded response per call and keep the rendered prompts."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def question_form(question: str) -> str | None:
    match = re.match(r"^\s*(how|what|why|when|who)\b", str(question or "").lower())
    return match.group(1) if match else None


def _normalized_contains(text: str, phrase: str) -> bool:
    return normalize_text(phrase) in normalize_text(text)


def evaluate_case(case: dict[str, Any], config: RecallConfig) -> dict[str, Any]:
    context = dict(case.get("context") or {})
    model = ReplayChatModel(case["response"])
    result = generate_question_with_answer(
        case["candidate_text"],
        case.get("item_type") or "fact",
        context,
        model,
        config=config,
    )
    prompt = model.prompts[0] if model.prompts else ""
    answer = result.get("answer") or ""
    expected = case.get("expected") or {}
    related_snippets = context.get("related_snippets") or []
    answer_points = expected.get("answer_points") or []
    matched_points = [
        point for point in answer_points if _normalized_contains(answer, point)
    ]
    missing_prompt_snippets = [
        snippet for snippet in related_snippets if snippet not in prompt
    ]
    is_multi_note = len(related_snippets) >= 2

    checks = {
        "pair_generated": result["status"] == "generated",
        "question_form": question_form(result.get("question") or "")
        == expected.get("question_form"),
        "answer_points": bool(answer_points) and len(matched_points) == len(answer_points),
        "prompt_context": not missing_prompt_snippets,
    }
    if is_multi_note:
        checks["multi_note"] = checks["answer_points"] and checks["prompt_context"]

    return {
        "id": case["id"],
        "question": result.get("question"),
        "answer": answer,
        "status": result["status"],
        "reason": result.get("reason"),
        "expected_question_form": expected.get("question_form"),
        "actual_question_form": question_form(result.get("question") or ""),
        "answer_points": answer_points,
        "matched_answer_points": matched_points,
        "related_snippet_count": len(related_snippets),
        "missing_prompt_snippets": missing_prompt_snippets,
        "checks": checks,
        "passed": all(checks.values()),
    }


def _rate(passed: int, total: int) -> float | None:
    return passed / total if total else None


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    config = RecallConfig()
    results = [evaluate_case(case, config) for case in cases]
    multi_note = [result for result in results if "multi_note" in result["checks"]]
    summary = {
        "case_count": len(results),
        "passed": sum(1 for result in results if result["passed"]),
        "pass_rate": _rate(sum(1 for result in results if result["passed"]), len(results)),
        "pair_generated_rate": _rate(
            sum(1 for result in results if result["checks"]["pair_generated"]),
            len(results),
        ),
        "question_form_rate": _rate(
            sum(1 for result in results if result["checks"]["question_form"]),
            len(results),
        ),
        "answer_point_rate": _rate(
            sum(1 for result in results if result["checks"]["answer_points"]),
            len(results),
        ),
        "prompt_context_rate": _rate(
            sum(1 for result in results if result["checks"]["prompt_context"]),
            len(results),
        ),
        "multi_note_case_count": len(multi_note),
        "multi_note_pass_count": sum(
            1 for result in multi_note if result["checks"]["multi_note"]
        ),
    }
    return {
        "runner": "recall_generation_replay",
        "code_revision": git_revision(),
        "configuration": {
            "max_attempts": config.max_attempts,
            "min_answer_overlap": config.min_answer_overlap,
        },
        "summary": summary,
        "cases": results,
    }


def _format_rate(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.3f}"


def format_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# NorthStar Recall Generation Evaluation",
        "",
        f"- Runner: `{report['runner']}`",
        f"- Code revision: `{report['code_revision']}`",
        f"- Cases: {summary['case_count']}",
        "",
        "## Summary",
        "",
        "| Metric | Result |",
        "| --- | ---: |",
        f"| Pair generated | {_format_rate(summary['pair_generated_rate'])} |",
        f"| Question form matched | {_format_rate(summary['question_form_rate'])} |",
        f"| Answer points covered | {_format_rate(summary['answer_point_rate'])} |",
        f"| Related-note context in prompt | {_format_rate(summary['prompt_context_rate'])} |",
        f"| Multi-note cases passed | {summary['multi_note_pass_count']}/{summary['multi_note_case_count']} |",
        f"| Overall pass rate | {_format_rate(summary['pass_rate'])} |",
        "",
        "## Cases",
        "",
        "| Case | Expected form | Actual form | Pair | Points | Context | Multi-note | Pass |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in report["cases"]:
        checks = result["checks"]
        lines.append(
            "| {case} | {expected} | {actual} | {pair} | {points} | {context} | {multi} | {passed} |".format(
                case=result["id"],
                expected=result["expected_question_form"],
                actual=result["actual_question_form"],
                pair="Pass" if checks["pair_generated"] else "Fail",
                points="Pass" if checks["answer_points"] else "Fail",
                context="Pass" if checks["prompt_context"] else "Fail",
                multi=(
                    "N/A"
                    if "multi_note" not in checks
                    else ("Pass" if checks["multi_note"] else "Fail")
                ),
                passed="Pass" if result["passed"] else "Fail",
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This runner replays recorded model responses through the production prompt builder and validators. It is a deterministic regression check for question-form matching, answer grounding, answer-point coverage, and multi-note context plumbing. It does not measure live model quality, latency, or cost.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the deterministic NorthStar recall generation regression evaluation."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULTS_PATH)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="Exit non-zero when any case fails its contract checks.",
    )
    args = parser.parse_args()

    report = evaluate(load_jsonl(args.cases))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_output = args.markdown_output or args.output.with_suffix(".md")
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(format_markdown(report), encoding="utf-8")

    print(json.dumps(report["summary"], indent=2))
    print(f"Wrote report: {args.output}")
    print(f"Wrote Markdown report: {markdown_output}")
    if args.fail_on_error and report["summary"]["passed"] != report["summary"]["case_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
