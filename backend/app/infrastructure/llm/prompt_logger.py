import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def get_log_path() -> Path:
    """Get the path for the prompt log file."""
    configured_dir = os.getenv("PROMPT_LOG_DIR")
    candidate_dirs = []

    if configured_dir:
        candidate_dirs.append(Path(configured_dir))

    backend_dir = Path(__file__).resolve().parent.parent.parent
    candidate_dirs.append(backend_dir / "logs")
    candidate_dirs.append(Path.cwd() / "logs")
    candidate_dirs.append(Path(tempfile.gettempdir()) / "northstar_logs")

    for log_dir in candidate_dirs:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            return log_dir / "gemini_prompt_response.txt"
        except OSError:
            continue

    raise RuntimeError("Unable to create a writable directory for prompt logs")


def log_gemini_interaction(
    note_text: str,
    related_notes: list[dict] | None,
    prompt: str,
    response: str,
    parsed_result: dict | None = None,
    parse_error: str | None = None,
):
    """
    Log the complete Gemini interaction to a file.
    The file is overwritten on each call to track the latest request.
    """
    try:
        log_path = get_log_path()
        timestamp = datetime.now(timezone.utc).isoformat()

        with open(log_path, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write(f"GEMINI INTERACTION LOG - {timestamp}\n")
            f.write("=" * 80 + "\n\n")

            # User Input
            f.write("### USER NOTE INPUT ###\n")
            f.write("-" * 80 + "\n")
            f.write(note_text)
            f.write("\n\n")

            # RAG Context
            f.write("### RAG CONTEXT (RELATED NOTES) ###\n")
            f.write("-" * 80 + "\n")
            if related_notes:
                f.write(f"✓ FOUND {len(related_notes)} RELATED NOTE(S):\n\n")
                for idx, note in enumerate(related_notes, 1):
                    f.write(f"[{idx}] Note ID: {note.get('note_id', 'unknown')}\n")
                    # Distance (lower is more similar) or similarity score (higher is more similar)
                    if 'distance' in note:
                        f.write(f"    Distance: {note.get('distance', 'N/A')} (lower = more similar)\n")
                    elif 'similarity_score' in note:
                        f.write(f"    Similarity Score: {note.get('similarity_score', 'N/A')}\n")
                    f.write(f"    Text: {note.get('text', '')}\n")
                    f.write(f"    Summary: {note.get('summary', '')}\n")
                    f.write("\n")
            else:
                f.write("✗ NO RELATED NOTES RETRIEVED (RAG not enabled or no matches)\n\n")

            # Full Prompt
            f.write("### FULL PROMPT SENT TO GEMINI ###\n")
            f.write("-" * 80 + "\n")
            f.write(prompt)
            f.write("\n\n")

            # Raw Response
            f.write("### RAW GEMINI RESPONSE ###\n")
            f.write("-" * 80 + "\n")
            f.write(response)
            f.write("\n\n")

            if parse_error:
                f.write("### PARSE ERROR ###\n")
                f.write("-" * 80 + "\n")
                f.write(parse_error)
                f.write("\n\n")

            # Parsed Result
            if parsed_result:
                f.write("### PARSED & NORMALIZED RESULT ###\n")
                f.write("-" * 80 + "\n")
                f.write(f"Summary: {parsed_result.get('summary', '')}\n\n")
                f.write(f"Tasks: {len(parsed_result.get('tasks', []))}\n")
                for task in parsed_result.get('tasks', []):
                    f.write(f"  - {task.get('description', '')}\n")
                f.write(f"\nFacts: {len(parsed_result.get('facts', []))}\n")
                for fact in parsed_result.get('facts', []):
                    f.write(f"  - {fact.get('content', '')}\n")
                f.write(f"\nQuestions: {len(parsed_result.get('questions', []))}\n")
                for q in parsed_result.get('questions', []):
                    f.write(f"  - {q.get('question', '')}\n")
                f.write(f"\nDecisions: {len(parsed_result.get('decisions', []))}\n")
                for d in parsed_result.get('decisions', []):
                    f.write(f"  - {d.get('decision', '')} (Rationale: {d.get('rationale', '')})\n")
                f.write(f"\nRisks: {len(parsed_result.get('risks', []))}\n")
                for r in parsed_result.get('risks', []):
                    f.write(f"  - {r.get('risk', '')} [Severity: {r.get('severity', 'unknown')}]\n")
                f.write(f"\nEntities: {len(parsed_result.get('entities', []))}\n")
                for e in parsed_result.get('entities', []):
                    f.write(f"  - {e.get('name', '')} ({e.get('entity_type', 'unknown')})\n")
                for c in parsed_result.get('concepts', []):
                    f.write(f"  - {c.get('concept', '')} (Confidence: {c.get('confidence', 'unknown')})\n")
                f.write("\n")

            f.write("=" * 80 + "\n")
            f.write("END OF LOG\n")
            f.write("=" * 80 + "\n")

        print(f"[PROMPT_LOGGER] Log written to: {log_path}")
    except Exception as exc:
        print(f"[PROMPT_LOGGER] Failed to write log file: {exc}")


def append_deterministic_resolution_log(
    note_id: str,
    user_id: str,
    resolution: dict[str, Any],
) -> None:
    """Append deterministic task-resolution diagnostics to the prompt log."""
    try:
        log_path = get_log_path()
        timestamp = datetime.now(timezone.utc).isoformat()
        updated_tasks = resolution.get("updated_tasks", []) or []
        diagnostics = resolution.get("diagnostics", {}) or {}
        candidates = diagnostics.get("candidate_matches", []) or []

        related_source_notes = sorted(
            {
                candidate.get("source_note_id")
                for candidate in candidates
                if candidate.get("source_note_id")
            }
        )

        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n")
            f.write("### DETERMINISTIC TASK RESOLUTION ###\n")
            f.write("-" * 80 + "\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"User ID: {user_id}\n")
            f.write(f"Source Note ID: {note_id}\n")
            f.write(f"Completion marker detected: {diagnostics.get('completion_detected')}\n")
            f.write(f"Open tasks checked: {diagnostics.get('open_task_count')}\n")
            f.write(f"Top overlap score: {diagnostics.get('top_score')}\n")
            f.write(f"Selection blocked reason: {diagnostics.get('selection_blocked_reason')}\n")
            f.write(f"Related source notes with similar tasks: {related_source_notes}\n")
            f.write(f"Candidate matches found: {len(candidates)}\n")
            if candidates:
                for idx, candidate in enumerate(candidates, start=1):
                    f.write(
                        f"  [{idx}] task_id={candidate.get('task_id')} | "
                        f"source_note_id={candidate.get('source_note_id')} | "
                        f"overlap={candidate.get('overlap_score')} | "
                        f"matched_tokens={candidate.get('matched_tokens')}\n"
                    )
                    f.write(f"      description={candidate.get('description')}\n")
            else:
                f.write("  (none)\n")

            f.write(f"Tasks updated via deterministic resolution: {len(updated_tasks)}\n")
            if updated_tasks:
                for task in updated_tasks:
                    f.write(
                        f"  - task_id={task.get('task_id')} | status={task.get('status')} | "
                        f"source_note_id={task.get('source_note_id')} | "
                        f"description={task.get('description')}\n"
                    )
            else:
                f.write("  (none)\n")
            f.write("\n")
            f.write(f"Concepts updated via deterministic resolution: {len(resolution.get('updated_concepts', []))}\n")
            if resolution.get("updated_concepts"):
                for concept in resolution.get("updated_concepts", []):
                    f.write(
                        f"  - concept_id={concept.get('concept_id')} | concept={concept.get('concept')} | "
                        f"confidence={concept.get('confidence')} | source_note_id={concept.get('source_note_id')}\n"
                    )
            else:
                f.write("  (none)\n")

        print(f"[PROMPT_LOGGER] Deterministic resolution log appended to: {log_path}")
    except Exception as exc:
        print(f"[PROMPT_LOGGER] Failed to append deterministic resolution log: {exc}")


def append_pipeline_log(stage: str, lines: list[str]) -> None:
    """Append a short pipeline trace to the shared Gemini log file."""
    try:
        log_path = get_log_path()
        timestamp = datetime.now(timezone.utc).isoformat()
        safe_lines = [str(line).strip() for line in lines if str(line).strip()]

        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n")
            f.write(f"### {stage.upper()} ###\n")
            f.write("-" * 80 + "\n")
            f.write(f"Timestamp: {timestamp}\n")
            for line in safe_lines:
                f.write(f"- {line}\n")

        print(f"[PROMPT_LOGGER] Pipeline log appended to: {log_path}")
    except Exception as exc:
        print(f"[PROMPT_LOGGER] Failed to append pipeline log: {exc}")
