"""Long-running SQS consumer for note-processing jobs.

This is the EC2-native replacement for the manual
``POST /notes/poll/process-jobs`` debug endpoint. Run it as its own systemd
service so note-processing CPU never competes with API request handling:

    python -m app.workers.sqs_consumer

Failed jobs are intentionally **not** deleted so SQS redelivers them and the
queue's redrive policy can move poison messages to the DLQ.
"""
from __future__ import annotations

import logging
import signal
import time

from ..infrastructure.queue.sqs_poller import delete_sqs_message, poll_sqs_messages
from .note_processor import process_sqs_message

logger = logging.getLogger(__name__)

_stopping = False


def _handle_stop(signum: int, _frame: object) -> None:
    global _stopping
    logger.info("Received signal %s; finishing in-flight job then stopping", signum)
    _stopping = True


def run_forever(max_messages: int = 5, wait_time_seconds: int = 20) -> None:
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    logger.info(
        "SQS consumer starting (max_messages=%s, wait_time_seconds=%s)",
        max_messages,
        wait_time_seconds,
    )
    while not _stopping:
        messages = poll_sqs_messages(
            max_messages=max_messages,
            wait_time_seconds=wait_time_seconds,
        )
        if not messages:
            continue

        for message in messages:
            if _stopping:
                break
            try:
                result = process_sqs_message(message["body"])
                logger.info("Processed message %s: %s", message["message_id"], result)
                if not delete_sqs_message(message["receipt_handle"]):
                    logger.warning(
                        "Processed message %s but failed to delete it; it may be redelivered",
                        message["message_id"],
                    )
            except Exception:
                logger.exception(
                    "Message %s failed; leaving it for SQS retry/DLQ",
                    message["message_id"],
                )

    logger.info("SQS consumer stopped")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    run_forever()
