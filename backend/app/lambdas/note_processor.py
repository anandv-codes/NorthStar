import os
import json
import logging
from datetime import datetime, timezone

from ..services.supabase import update_note_item
from ..services.langchain import call_gemini_api
from ..services.embeddings import get_embeddings
from ..services.vectorstore import query_related_notes, upsert_note_embedding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
ENABLE_RAG = os.getenv("ENABLE_RAG", "false").lower() == "true"

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
            # TODO: Implement embeddings.py and vectorstore.py first.
            # Then this branch retrieves prior notes before synthesis.
            note_embedding = get_embeddings().embed_query(raw_text)
            related_notes = query_related_notes(
                user_id=user_id,
                embedding=note_embedding,
                k=3,
                exclude_note_id=note_id,
            )

        enrichment_res = call_gemini_api(raw_text, related_notes=related_notes)
        logger.info(f"Bedrock response: {enrichment_res}")
        enriched_text= enrichment_res.get("summary","")
        logger.info(f"Bedrock returned : {enriched_text[:100]}")
        updates = {
            "status": "completed",
            "enriched_summary": enrichment_res.get("summary", ""),
            "action_items": enrichment_res.get("action_items", []),
            "questions": enrichment_res.get("questions", []),
            "insights": enrichment_res.get("insights", []),
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Updating db")
        update_note_item(user_id,note_id,updates)

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
