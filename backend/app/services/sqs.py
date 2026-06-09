import os
import json
import boto3

SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123456789012/northstar-note-jobs")
AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL")

sqs = boto3.client("sqs", endpoint_url=AWS_ENDPOINT_URL)

def send_note_job(payload: dict) -> dict:
    response = sqs.send_message(QueueUrl=SQS_QUEUE_URL, MessageBody=json.dumps(payload))
    return response
