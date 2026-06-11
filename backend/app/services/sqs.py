import os
import json
import boto3

SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123456789012/northstar-note-jobs")
AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL") or None

sqs = boto3.client("sqs", endpoint_url=AWS_ENDPOINT_URL)

def send_note_job(payload: dict) -> dict:
    note_id = payload.get("note_id") or "default"
    print(f"[SQS] Sending job to queue for note_id={note_id}")
    message_args = {
        "QueueUrl": SQS_QUEUE_URL,
        "MessageBody": json.dumps(payload),
        "MessageGroupId": note_id,
        "ModelId": os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-2"),
    }
    if SQS_QUEUE_URL.endswith(".fifo"):
        message_args["MessageDeduplicationId"] = note_id

    response = sqs.send_message(**message_args)
    print(f"[SQS] Job sent successfully, MessageId={response.get('MessageId')}")
    return response
