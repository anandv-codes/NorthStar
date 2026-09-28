import os
import json
import logging
from datetime import datetime, timezone

from ..infrastructure.db.supabase_client import update_note_item
from ..infrastructure.llm.gemini_client import call_gemini_api
from ..infrastructure.vector.embeddings import get_embeddings
from ..domain.memory.services import (
    apply_deterministic_task_resolution,
    create_extraction_run,
    insert_decisions,
    insert_facts,
    insert_memory_item_entity_links,
    insert_questions,
    insert_risks,
    insert_tasks,
    insert_concepts,
    upsert_entities,
)
from ..infrastructure.llm.prompt_logger import append_deterministic_resolution_log
from ..infrastructure.vector.vectorstore import upsert_note_embedding
from ..domain.query_retrieval.note_context_provider import fetch_note_context

logger = logging.getLogger()
logger.setLevel(logging.INFO)

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

        # Phase A + R: Fetch context via BOTH hybrid semantic retrieval AND entity-linked deterministic matching.
        try:
            context_result = fetch_note_context(
                user_id=user_id,
                raw_text=raw_text,
                limit_hybrid=3,
                exclude_note_id=note_id,
            )
            related_notes = context_result.get("related_notes", [])
            matched_entity_names = context_result.get("matched_entity_names", [])
            memory_items = context_result.get("memory_items", [])
            retrieval_sources = context_result.get("retrieval_sources", {})
            
            logger.info(
                f"Context retrieval: {retrieval_sources.get('hybrid_count', 0)} hybrid + "
                f"{retrieval_sources.get('entity_linked_count', 0)} entity-linked = "
                f"{retrieval_sources.get('merged_note_count', 0)} merged notes, "
                f"{len(matched_entity_names)} entity names matched, "
                f"{retrieval_sources.get('memory_items_count', 0)} memory items"
            )
        except Exception as exc:
            logger.warning(f"Context retrieval failed; continuing without related context: {exc}")
            related_notes = []
            matched_entity_names = []
            memory_items = []

        # Get embedding for later upsert to vector store.
        try:
            note_embedding = get_embeddings().embed_query(raw_text)
        except Exception as exc:
            logger.warning(f"Embedding generation failed; continuing without vector upsert: {exc}")
            note_embedding = None

        enrichment_res = call_gemini_api(
            raw_text,
            related_notes=related_notes,
            matched_entity_names=matched_entity_names,
            memory_items=memory_items,
        )
        logger.info(f"Gemini response: {enrichment_res}")
        enriched_text= enrichment_res.get("summary","")
        logger.info(f"Bedrock returned : {enriched_text[:100]}")
        extraction_run = create_extraction_run(
            user_id=user_id,
            note_id=note_id,
            model_name=os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash"),
            prompt_version=os.getenv("WORK_MEMORY_PROMPT_VERSION", "phase3-v1"),
            status="completed",
        )

        # Extract context note IDs from both hybrid and entity-linked retrieval.
        context_note_ids = [note.get("note_id") for note in related_notes if note.get("note_id")]
        # Deduplicate while preserving order.
        seen = set()
        context_note_ids_dedup = []
        for nid in context_note_ids:
            if nid not in seen:
                context_note_ids_dedup.append(nid)
                seen.add(nid)

        updates = {
            "status": "completed",
            "enriched_summary": enrichment_res.get("summary", ""),
            "context_note_ids": context_note_ids_dedup,
            "action_items": [item["description"] for item in enrichment_res.get("tasks", [])],
            "questions": [item["question"] for item in enrichment_res.get("questions", [])],
            "insights": [],
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Updating db")
        update_note_item(user_id,note_id,updates)

        tasks = insert_tasks(
            user_id=user_id,
            source_note_id=note_id,
            extraction_run_id=extraction_run["extraction_run_id"],
            tasks=enrichment_res.get("tasks", []),
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
        risks = insert_risks(
            user_id=user_id,
            source_note_id=note_id,
            extraction_run_id=extraction_run["extraction_run_id"],
            risks=enrichment_res.get("risks", []),
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
        add_links(risks, "risk", "risk_id")
        add_links(concepts, "concept", "concept_id")

        if links:
            insert_memory_item_entity_links(
                user_id=user_id,
                source_note_id=note_id,
                links=links,
            )

        resolution = apply_deterministic_task_resolution(
            user_id=user_id,
            raw_text=raw_text,
            source_note_id=note_id,
            include_diagnostics=True,
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

        # RAG is always enabled: upsert the embedding to the vector store for future retrieval.
        if note_embedding is not None:
            # Upsert after the DB update so failed enrichment does not pollute
            # the local vector index.
            upsert_note_embedding(
                user_id=user_id,
                note_id=note_id,
                text=raw_text,
                embedding=note_embedding,
                metadata={"summary": enrichment_res.get("summary", "")},
            )

        return {
            "success": True,
            "note_id": note_id,
        }
    except Exception as e:
        logger.error(f"Error!!! {str(e)}")
        raise #Re-raise so AWS knows to retry




def lambda_handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    batch_failures = []
    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            process_sqs_message(body)
        except Exception as e:
            logger.error(f"Error processing record: {e}")
            batch_failures.append({"itemIdentifier": record["messageId"]})
    return {"statusCode": 200, "body": "Processing complete", "batchItemFailures": batch_failures}

# For testing

# if __name__ == "__main__":
#     mock_event = {
#         "Records": [
#             {
#                 "messageId": "1",
#                 "body": json.dumps({
#                     "user_id": "user-123",
#                     "note_id": "3fc0fa04-dfa7-4b29-a405-ff73f1d168c0",
#                     "created_at": '2026-06-13 12:17:40.336919+00',
#                     "raw_text": "This is a test note. TODO: Follow up with team. What is the status of the project?"
#                 }),

#             }
#         ]
#     }
#     print("Testing lambda handler with mock event")
#     result=lambda_handler(mock_event, context=None)
#     print(f"Result: {result}")
