import os
import json
import logging
import time
from datetime import datetime, timezone

from ..infrastructure.db.supabase_client import get_note_item, update_note_item
from ..infrastructure.llm.gemini_client import (
    DEFAULT_GEMINI_MODEL_ID,
    call_gemini_api,
    get_chat_model,
)
from ..domain.memory.services import (
    apply_deterministic_task_resolution,
    begin_extraction_run,
    bump_entity_mentions,
    ingest_note_memories,
    save_extraction_payload,
)
from ..domain.memory.extraction_v2 import (
    build_note_metadata,
    entity_importance_delta,
    task_rows_with_scoring,
)
from ..domain.memory.note_status import validate_note_status_transition
from ..domain.recall.candidate_service import generate_candidates
from ..domain.recall.question_service import build_context, generate_questions
from ..infrastructure.db.commitment_repository import get_commitment_repository
from ..infrastructure.db.recall_repository import get_recall_repository
from ..infrastructure.llm.prompt_logger import append_deterministic_resolution_log
from ..infrastructure.vector.vectorstore import index_note
from ..domain.query_retrieval.note_context_provider import fetch_note_context

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class _StageTimer:
    """Collect per-stage durations so a slow note shows up as one log line."""

    def __init__(self) -> None:
        self.timings: dict[str, float] = {}
        self._last = time.perf_counter()

    def mark(self, stage: str) -> None:
        now = time.perf_counter()
        self.timings[stage] = round((now - self._last) * 1000, 1)
        self._last = now

    @property
    def total_ms(self) -> float:
        return round(sum(self.timings.values()), 1)


def _finalize_note(
    *,
    user_id: str,
    note_id: str,
    status: str,
    recall_status: str,
    indexed_at: str | None = None,
    index_error: str | None = None,
) -> None:
    """Write the terminal status without failing an already-processed note.

    Best-effort on purpose: the typed memories and vectors are already
    persisted, so a status-write hiccup should be logged rather than trigger a
    full SQS redelivery (which would re-run the LLM).
    """
    payload: dict[str, object] = {"status": status, "recall_status": recall_status}
    if indexed_at:
        payload["indexed_at"] = indexed_at
    if index_error:
        payload["index_error"] = index_error
    try:
        update_note_item(user_id, note_id, payload)
    except Exception as exc:
        logger.warning(
            f"Could not persist terminal status {status} for note {note_id}: {exc}"
        )


def process_sqs_message(body:dict)-> dict:
    ##Extract data & call Gemini
    ##DB update & return success
    try:
        note_id = body.get("note_id")
        user_id = body.get("user_id",0)
        raw_text = body.get("raw_text","")

        if not note_id or not user_id or not raw_text:
            raise ValueError(f"Missing required fields")
        logger.info(f"Processing {note_id} for user {user_id}")
        timer = _StageTimer()

        # Per-note opt-in: question+answer pairs (the LLM cost in the recall
        # loop) are generated only when the user enabled recall for this note.
        # Candidates are still scored so toggling ON later is instant.
        try:
            note_row = get_note_item(user_id=user_id, note_id=note_id) or {}
        except Exception as exc:
            logger.warning(f"Could not read note recall flag; defaulting to off: {exc}")
            note_row = {}
        recall_enabled = bool(note_row.get("recall_enabled", False))
        recall_status = "off"
        note_status = str(note_row.get("status") or "processing")
        # `indexed` is terminal: a duplicate delivery of a finished note is
        # acknowledged instead of re-running extraction or failing the state
        # machine.
        if note_status == "indexed":
            logger.info(
                f"Note {note_id} is already indexed; acknowledging duplicate delivery"
            )
            return {"success": True, "note_id": note_id, "status": "indexed"}
        # A redelivered job re-enters the lifecycle instead of jumping straight
        # from `failed` to `enriched`, which the state machine rejects.
        if note_status == "failed":
            validate_note_status_transition(note_status, "processing")
            update_note_item(user_id, note_id, {"status": "processing", "index_error": None})
            note_status = "processing"
        logger.info(f"Recall generation enabled: {recall_enabled} for note {note_id}")

        # Fetch related notes from the hybrid retriever (BM25 + dense + RRF).
        try:
            context_result = fetch_note_context(
                user_id=user_id,
                raw_text=raw_text,
                limit_hybrid=3,
                exclude_note_id=note_id,
            )
            related_notes = context_result.get("related_notes", [])
            retrieval_sources = context_result.get("retrieval_sources", {})

            logger.info(
                f"Context retrieval: {retrieval_sources.get('hybrid_count', 0)} hybrid results, "
                f"{retrieval_sources.get('merged_note_count', 0)} notes after merge"
            )
        except Exception as exc:
            logger.warning(f"Context retrieval failed; continuing without related context: {exc}")
            related_notes = []
        timer.mark("retrieval")

        commitment_repo = get_commitment_repository()
        try:
            # The extraction prompt needs id + text only. Querying the repository
            # directly avoids the contribution-count query used by list views.
            active_commitments = commitment_repo.query_commitments(user_id, status="active")
        except Exception as exc:
            # Goal tracking must never break note ingestion.
            logger.warning(f"Could not load long-term goals; continuing without them: {exc}")
            active_commitments = []

        extraction_run = begin_extraction_run(
            user_id=user_id,
            note_id=note_id,
            model_name=os.getenv("GEMINI_MODEL_ID", DEFAULT_GEMINI_MODEL_ID),
            prompt_version=os.getenv("WORK_MEMORY_PROMPT_VERSION", "phase3-v1"),
        )
        extraction_run_id = extraction_run["extraction_run_id"]

        # The payload is written *before* the fan-out, so "payload present"
        # means the LLM call already happened: a redelivery replays it instead
        # of paying for the same extraction twice.
        stored_payload = extraction_run.get("payload")
        if stored_payload:
            logger.info(
                f"Replaying stored extraction payload for note {note_id} "
                f"(run {extraction_run_id}); skipping LLM"
            )
            enrichment_res = stored_payload
        else:
            enrichment_res = call_gemini_api(
                raw_text,
                related_notes=related_notes,
                commitments=active_commitments,
            )
            # Full prompt/response already persisted to file via
            # log_gemini_interaction in gemini_client.
            save_extraction_payload(extraction_run_id, enrichment_res)
        timer.mark("extraction")

        # Extract context note IDs from both hybrid and entity-linked retrieval.
        context_note_ids = [note.get("note_id") for note in related_notes if note.get("note_id")]
        # Deduplicate while preserving order.
        seen = set()
        context_note_ids_dedup = []
        for nid in context_note_ids:
            if nid not in seen:
                context_note_ids_dedup.append(nid)
                seen.add(nid)

        metadata_projection = build_note_metadata(enrichment_res)
        # Extraction is persisted from here on, so the note is `enriched`.
        # It is not retrievable until `index_note` below succeeds.
        validate_note_status_transition(note_status, "enriched")
        note_status = "enriched"
        updates = {
            "status": "enriched",
            "recall_status": "pending" if recall_enabled else "off",
            "enriched_summary": enrichment_res.get("summary", ""),
            "context_note_ids": context_note_ids_dedup,
            "action_items": [item["description"] for item in enrichment_res.get("tasks", [])],
            "questions": [item["question"] for item in enrichment_res.get("questions", [])],
            "insights": [],
            "metadata": metadata_projection,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Updating db")
        update_note_item(user_id,note_id,updates)
        timer.mark("db_update")

        # One transaction writes every typed row, entity, link, and goal
        # contribution. A replay returns the rows the first attempt wrote
        # instead of inserting them again.
        fanout_payload = {
            "tasks": task_rows_with_scoring(enrichment_res.get("tasks", [])),
            "facts": enrichment_res.get("facts", []),
            "questions": enrichment_res.get("questions", []),
            "decisions": enrichment_res.get("decisions", []),
            "concepts": enrichment_res.get("concepts", []),
            "entities": enrichment_res.get("entities", []),
            "commitment_contributions": enrichment_res.get(
                "commitment_contributions", []
            ),
        }
        fanout = ingest_note_memories(
            user_id=user_id,
            note_id=note_id,
            extraction_run_id=extraction_run_id,
            payload=fanout_payload,
        )
        tasks = fanout.get("tasks", [])
        facts = fanout.get("facts", [])
        questions = fanout.get("questions", [])
        decisions = fanout.get("decisions", [])
        concepts = fanout.get("concepts", [])
        entity_rows = fanout.get("entities", [])
        logger.info(
            "Fan-out %s: tasks=%d facts=%d questions=%d decisions=%d "
            "concepts=%d links=%d contributions=%d",
            "replayed" if fanout.get("duplicate") else "applied",
            len(tasks),
            len(facts),
            len(questions),
            len(decisions),
            len(concepts),
            fanout.get("links", 0),
            fanout.get("contributions", 0),
        )
        timer.mark("fanout")

        # Consolidation: entities seen across notes gain weight over time.
        # Skipped on a replay, where the first attempt already bumped them.
        entity_names = [entity.get("name") for entity in entity_rows if entity.get("name")]
        if entity_names and not fanout.get("duplicate"):
            try:
                bump_entity_mentions(
                    user_id=user_id,
                    names=entity_names,
                    importance_delta=entity_importance_delta(entity_names),
                )
            except Exception as exc:
                logger.warning(f"Entity importance update failed; continuing: {exc}")

        # PR6: score extracted units into recall candidates. Idempotent via
        # (user_id, dedupe_key) upsert, so re-processing a note is safe.
        # Re-read the flag: the user may have toggled recall ON while this note
        # was already processing (the start-of-run read would be stale).
        try:
            fresh_note = get_note_item(user_id=user_id, note_id=note_id) or {}
            recall_enabled = bool(fresh_note.get("recall_enabled", recall_enabled))
        except Exception as exc:
            logger.warning(f"Could not re-read recall flag; keeping {recall_enabled}: {exc}")

        try:
            candidates = generate_candidates(
                user_id=user_id,
                note_id=note_id,
                extraction=enrichment_res,
                related_note_ids=context_note_ids_dedup,
                entity_rows=entity_rows,
                typed_rows={
                    "task": tasks,
                    "fact": facts,
                    "question": questions,
                    "decision": decisions,
                    "concept": concepts,
                },
            )
            logger.info(f"Recall candidates created: {len(candidates)}")
            timer.mark("candidates")

            # PR7: generate the question and answer together (one LLM call per
            # candidate) in this async worker. Only when the user enabled
            # recall for this note.
            if recall_enabled:
                related_snippets = [
                    (note.get("summary") or note.get("raw_text") or "").strip()
                    for note in related_notes[:2]
                ]
                context = build_context(raw_text, related_snippets, entity_names)
                question_results = generate_questions(
                    candidates,
                    context,
                    model=get_chat_model(),
                    repo=get_recall_repository(),
                )
                suggested = sum(1 for r in question_results if r["status"] == "suggested")
                recall_status = "ready"
                logger.info(
                    f"Recall questions suggested: {suggested}/{len(question_results)}"
                )
            else:
                recall_status = "off"
                logger.info("Recall disabled for note; skipping question generation")
            timer.mark("questions")
        except Exception as exc:
            recall_status = "failed" if recall_enabled else "off"
            logger.warning(f"Candidate/question generation failed; continuing: {exc}")

        # Persist recall state now, but leave the note non-terminal: it is not
        # retrievable until `index_note` below succeeds.
        try:
            update_note_item(user_id, note_id, {"recall_status": recall_status})
        except Exception as exc:
            logger.warning(f"Could not persist recall status: {exc}")
        timer.mark("recall_status")

        resolution = apply_deterministic_task_resolution(
            user_id=user_id,
            raw_text=raw_text,
            source_note_id=note_id,
        )
        updated_tasks = resolution.get("updated_tasks", [])
        logger.info(
            f"Deterministic resolution updated {len(updated_tasks)} task(s) for note {note_id}",
        )
        append_deterministic_resolution_log(
            note_id=note_id,
            user_id=user_id,
            resolution=resolution,
        )
        timer.mark("resolution")

        # RAG is always enabled: chunk + embed the note and index it in
        # pgvector for future retrieval. Done last so failed enrichment does
        # not pollute the index. This is the step that makes the note
        # retrievable, so it also decides the terminal status: swallowing this
        # error used to leave a "completed" note retrieval could never find.
        try:
            chunk_count = index_note(
                user_id=user_id,
                note_id=note_id,
                text=raw_text,
            )
            logger.info(f"Indexed {chunk_count} chunk(s) for note {note_id}")
        except Exception as exc:
            logger.warning(f"Vector indexing failed; marking note failed: {exc}")
            validate_note_status_transition(note_status, "failed")
            note_status = "failed"
            _finalize_note(
                user_id=user_id,
                note_id=note_id,
                status="failed",
                recall_status=recall_status,
                index_error=str(exc)[:500],
            )
        else:
            validate_note_status_transition(note_status, "indexed")
            note_status = "indexed"
            _finalize_note(
                user_id=user_id,
                note_id=note_id,
                status="indexed",
                recall_status=recall_status,
                indexed_at=datetime.now(timezone.utc).isoformat(),
            )
        timer.mark("indexing")

        logger.info(
            "Note %s timings (ms): %s | total=%s",
            note_id,
            ", ".join(f"{stage}={ms}" for stage, ms in timer.timings.items()),
            timer.total_ms,
        )

        return {
            "success": note_status == "indexed",
            "note_id": note_id,
            "status": note_status,
        }
    except Exception as e:
        logger.exception(f"Note processing failed for note_id={body.get('note_id')} user_id={body.get('user_id')}: {e}")
        raise  # Re-raise so AWS knows to retry


def lambda_handler(event, context):
    records = event.get("Records", [])
    logger.info("Received %d SQS record(s)", len(records))
    batch_failures = []
    for record in records:
        try:
            body = json.loads(record["body"])
            process_sqs_message(body)
        except Exception as e:
            logger.error("Error processing record %s: %s", record.get("messageId"), e)
            batch_failures.append({"itemIdentifier": record["messageId"]})
    return {"statusCode": 200, "body": "Processing complete", "batchItemFailures": batch_failures}
