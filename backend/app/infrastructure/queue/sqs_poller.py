import os
import json
import logging
import boto3
from typing import Optional

logger = logging.getLogger(__name__)

SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123456789012/northstar-note-jobs")
AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL") or None

sqs = boto3.client("sqs", endpoint_url=AWS_ENDPOINT_URL)


def poll_sqs_messages(max_messages: int = 1, wait_time_seconds: int = 0) -> list[dict]:
    """Poll SQS queue for messages.

    Args:
        max_messages: Maximum number of messages to retrieve (1-10)
        wait_time_seconds: Long polling duration in seconds (0-20)

    Returns:
        List of SQS messages with parsed body
    """
    try:
        response = sqs.receive_message(
            QueueUrl=SQS_QUEUE_URL,
            MaxNumberOfMessages=min(max_messages, 10),
            WaitTimeSeconds=min(wait_time_seconds, 20),
        )

        messages = []
        for message in response.get("Messages", []):
            try:
                body = json.loads(message["Body"])
                messages.append({
                    "message_id": message["MessageId"],
                    "receipt_handle": message["ReceiptHandle"],
                    "body": body,
                })
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse message body: {e}")

        return messages
    except Exception as e:
        logger.error(f"Error polling SQS: {e}")
        return []


def delete_sqs_message(receipt_handle: str) -> bool:
    """Delete a message from the SQS queue.

    Args:
        receipt_handle: Receipt handle from the polled message

    Returns:
        True if successful, False otherwise
    """
    try:
        sqs.delete_message(
            QueueUrl=SQS_QUEUE_URL,
            ReceiptHandle=receipt_handle,
        )
        logger.info(f"Message deleted successfully")
        return True
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
        return False
