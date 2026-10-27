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
from ..domain.commitments.services import persist_note_contributions
from ..domain.memory.services import (
    apply_deterministic_task_resolution,
    bump_entity_mentions,
    create_extraction_run,
    insert_decisions,
    insert_facts,
    insert_memory_item_entity_links,
    insert_questions,
    insert_tasks,
    insert_concepts,
    upsert_entities,
)
from ..domain.memory.extraction_v2 import (
    build_note_metadata,
    entity_importance_delta,
    task_rows_with_scoring,
)
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

        enrichment_res = call_gemini_api(
            raw_text,
            related_notes=related_notes,
            commitments=active_commitments,
        )
        # Full prompt/response already persisted to file via log_gemini_interaction in gemini_client.
        enriched_text= enrichment_res.get("summary","")
        extraction_run = create_extraction_run(
            user_id=user_id,
            note_id=note_id,
            model_name=os.getenv("GEMINI_MODEL_ID", DEFAULT_GEMINI_MODEL_ID),
            prompt_version=os.getenv("WORK_MEMORY_PROMPT_VERSION", "phase3-v1"),
            status="completed",
        )
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
        updates = {
            # The note stays "processing" until the end of the pipeline, so
            # "completed" always implies recall questions are ready (when enabled).
            "status": "processing",
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

        tasks = insert_tasks(
            user_id=user_id,
            source_note_id=note_id,
            extraction_run_id=extraction_run["extraction_run_id"],
            tasks=task_rows_with_scoring(enrichment_res.get("tasks", [])),
        )
        facts = insert_facts(
            user_id=user_id,
            source_note_id=note_id,
            extraction_run_id=extraction_run["extraction_run_id"],
            facts=enrichment_res.get("facts", []),
        )
        questions = insert_questions(
            user_id=user_id,
            source_note_id=note_id,
            extraction_run_id=extraction_run["extraction_run_id"],
            questions=enrichment_res.get("questions", []),
        )
        decisions = insert_decisions(
            user_id=user_id,
            source_note_id=note_id,
            extraction_run_id=extraction_run["extraction_run_id"],
            decisions=enrichment_res.get("decisions", []),
        )
        concepts = insert_concepts(
            user_id=user_id,
            source_note_id=note_id,
            extraction_run_id=extraction_run["extraction_run_id"],
            concepts=enrichment_res.get("concepts", []),
        )
        entity_rows = upsert_entities(
            user_id=user_id,
            entities=enrichment_res.get("entities", []),
        )

        # Consolidation: entities seen across notes gain weight over time.
        entity_names = [entity.get("name") for entity in entity_rows if entity.get("name")]
        if entity_names:
            try:
                bump_entity_mentions(
                    user_id=user_id,
                    names=entity_names,
                    importance_delta=entity_importance_delta(entity_names),
                )
            except Exception as exc:
                logger.warning(f"Entity importance update failed; continuing: {exc}")

        try:
            contributions = persist_note_contributions(
                user_id=user_id,
                note_id=note_id,
                extraction=enrichment_res,
                repo=commitment_repo,
            )
            logger.info(f"Long-term goal contributions added: {len(contributions)}")
        except Exception as exc:
            logger.warning(f"Commitment contribution persistence failed; continuing: {exc}")
        timer.mark("commitments")

        entity_name_to_id = {
            str(entity.get("name", "")).strip().lower(): entity.get("entity_id")
            for entity in entity_rows
            if entity.get("name")
        }
        links = []

        def add_links(items: list[dict], item_type: str, id_key: str) -> None:
            for item in items:
                item_id = item.get(id_key)
                if not item_id:
                    continue
                for entity_name in item.get("entities", []):
                    entity_id = entity_name_to_id.get(str(entity_name).strip().lower())
                    if entity_id:
                        links.append(
                            {
                                "entity_id": entity_id,
                                "item_type": item_type,
                                "item_id": item_id,
                            }
                        )

        add_links(tasks, "task", "task_id")
        add_links(facts, "fact", "fact_id")
        add_links(questions, "question", "question_id")
        add_links(decisions, "decision", "decision_id")
        add_links(concepts, "concept", "concept_id")

        if links:
            insert_memory_item_entity_links(
                user_id=user_id,
                source_note_id=note_id,
                links=links,
            )
        logger.info(f"Entity links created: {len(links)}")
        timer.mark("entity_links")

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

        # Finalize the note: "completed" only once question generation has
        # finished (or failed). Always set it here rather than before inserts so
        # a toggle racing with processing can rely on the status.
        try:
            update_note_item(
                user_id, note_id, {"status": "completed", "recall_status": recall_status}
            )
        except Exception as exc:
            logger.warning(f"Could not finalize note recall status: {exc}")
        timer.mark("finalize")

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
        # not pollute the index.
        try:
            chunk_count = index_note(
                user_id=user_id,
                note_id=note_id,
                text=raw_text,
            )
            logger.info(f"Indexed {chunk_count} chunk(s) for note {note_id}")
        except Exception as exc:
            logger.warning(f"Vector indexing failed; note stored without embeddings: {exc}")
        timer.mark("indexing")

        logger.info(
            "Note %s timings (ms): %s | total=%s",
            note_id,
            ", ".join(f"{stage}={ms}" for stage, ms in timer.timings.items()),
            timer.total_ms,
        )

        return {
            "success": True,
            "note_id": note_id,
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
