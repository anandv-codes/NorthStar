"""Evaluate the hybrid intent router against a labeled validation set.

Default mode uses the local sentence-transformers kNN classifier. Use
``--rules-only`` for a deterministic baseline that needs no model download.
The validation set is deliberately separate from the seed utterances.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from backend.app.domain.routing.classifier import HybridIntentClassifier
from backend.app.domain.routing.contracts import IntentContext
from backend.app.domain.routing.embedding_intent import LocalSemanticIntentClassifier
from backend.app.domain.routing.rules import (
    build_conversation_rule,
    build_retrieval_rule,
    build_status_rule,
    build_tool_rule,
)

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES_PATH = WORKSPACE_ROOT / "evals" / "datasets" / "northstar_intent_v1.jsonl"
RESULTS_DIR = WORKSPACE_ROOT / "evals" / "results"
LABELS = ("conversation", "note_content", "note_status", "action")


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


def build_classifier(args: argparse.Namespace) -> HybridIntentClassifier:
    rules = (
        build_tool_rule(),
        build_status_rule(),
        build_retrieval_rule(),
        build_conversation_rule(),
    )
    semantic = None
    if not args.rules_only:
        if importlib.util.find_spec("sentence_transformers") is None:
            raise SystemExit(
                "sentence-transformers is not installed. Install backend requirements "
                "or rerun with --rules-only."
            )
        semantic = LocalSemanticIntentClassifier(
            threshold=args.threshold,
            margin=args.margin,
            top_examples_per_label=args.top_examples,
        )
    return HybridIntentClassifier(rules=rules, semantic_classifier=semantic)


def evaluate(cases: list[dict[str, Any]], classifier: HybridIntentClassifier) -> dict[str, Any]:
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    rows: list[dict[str, Any]] = []
    for case in cases:
        expected = str(case["label"])
        decision = classifier.classify(
            IntentContext(surface="intent_eval", message=str(case["text"]))
        )
        predicted = decision.kind
        confusion[expected][predicted] += 1
        rows.append(
            {
                "text": case["text"],
                "expected": expected,
                "predicted": predicted,
                "correct": expected == predicted,
                "confidence": decision.confidence,
                "grounding_mode": decision.grounding_mode,
                "reasons": list(decision.reasons),
            }
        )

    correct = sum(1 for row in rows if row["correct"])
    per_label: dict[str, dict[str, float | int]] = {}
    for label in LABELS:
        true_positive = confusion[label][label]
        predicted_count = sum(confusion[other][label] for other in LABELS)
        support = sum(confusion[label].values())
        precision = true_positive / predicted_count if predicted_count else 0.0
        recall = true_positive / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "support": support,
        }

    return {
        "case_count": len(rows),
        "accuracy": round(correct / len(rows), 3) if rows else 0.0,
        "action_precision": per_label["action"]["precision"],
        "per_label": per_label,
        "confusion": {label: dict(confusion[label]) for label in LABELS},
        "cases": rows,
    }


def format_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    configuration = report["configuration"]
    lines = [
        "# NorthStar Intent Evaluation",
        "",
        f"- Runner: `{report['runner']}`",
        f"- Code revision: `{report['code_revision']}`",
        f"- Configuration: `threshold={configuration['threshold']}`, "
        f"`margin={configuration['margin']}`, "
        f"`top_examples={configuration['top_examples']}`",
        f"- Cases: {summary['case_count']}",
        f"- Accuracy: {summary['accuracy']:.3f}",
        f"- Action precision: {summary['action_precision']:.3f}",
        "",
        "## Per-label",
        "",
        "| Label | Precision | Recall | F1 | Support |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for label in LABELS:
        row = summary["per_label"][label]
        lines.append(
            f"| {label} | {row['precision']:.3f} | {row['recall']:.3f} | "
            f"{row['f1']:.3f} | {row['support']} |"
        )
    lines.extend(["", "## Confusion", "", "| Expected | Predicted | Count |", "| --- | --- | ---: |"])
    for expected in LABELS:
        for predicted, count in summary["confusion"].get(expected, {}).items():
            lines.append(f"| {expected} | {predicted} | {count} |")
    lines.extend(["", "## Cases", "", "| Expected | Predicted | Confidence | Text |", "| --- | --- | ---: | --- |"])
    for row in summary["cases"]:
        text = str(row["text"]).replace("|", "\\|")
        lines.append(
            f"| {row['expected']} | {row['predicted']} | {row['confidence']:.2f} | {text} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--rules-only", action="store_true")
    parser.add_argument("--threshold", type=float, default=0.42)
    parser.add_argument("--margin", type=float, default=0.03)
    parser.add_argument("--top-examples", type=int, default=2)
    args = parser.parse_args()

    cases = load_jsonl(args.cases)
    classifier = build_classifier(args)
    summary = evaluate(cases, classifier)
    mode = "rules" if args.rules_only else "hybrid"
    report = {
        "runner": f"intent_{mode}",
        "code_revision": git_revision(),
        "configuration": {
            "mode": mode,
            "threshold": args.threshold,
            "margin": args.margin,
            "top_examples": args.top_examples,
        },
        "summary": summary,
    }

    output_path = args.output or RESULTS_DIR / f"northstar_intent_v1_{mode}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    output_path.with_suffix(".md").write_text(format_markdown(report), encoding="utf-8")

    print(f"accuracy={summary['accuracy']:.3f} action_precision={summary['action_precision']:.3f}")
    for label in LABELS:
        row = summary["per_label"][label]
        print(
            f"{label}: precision={row['precision']:.3f} recall={row['recall']:.3f} "
            f"f1={row['f1']:.3f} support={row['support']}"
        )
    print(f"wrote {output_path} and {output_path.with_suffix('.md')}")


if __name__ == "__main__":
    main()
