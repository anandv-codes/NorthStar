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
from ..infrastructure.vector.vectorstore import query_related_notes, upsert_note_embedding

logger = logging.getLogger()
logger.setLevel(logging.INFO)
ENABLE_RAG = os.getenv("ENABLE_RAG", "false").strip().lower() == "true"

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

        related_notes = []
        note_embedding = None
        if ENABLE_RAG:
            try:
                note_embedding = get_embeddings().embed_query(raw_text)
                related_notes = query_related_notes(
                    user_id=user_id,
                    embedding=note_embedding,
                    k=3,
                    exclude_note_id=note_id,
                )
            except Exception as exc:
                logger.warning(f"RAG embeddings failed; continuing without related notes: {exc}")

        enrichment_res = call_gemini_api(raw_text, related_notes=related_notes)
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

        updates = {
            "status": "completed",
            "enriched_summary": enrichment_res.get("summary", ""),
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

        if ENABLE_RAG and note_embedding is not None:
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
