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
from datetime import datetime, timezone

from ..infrastructure.queue.sqs_poller import delete_sqs_message, poll_sqs_messages
from ..observability import log_timing_event
from .note_processor import process_sqs_message

logger = logging.getLogger(__name__)

_stopping = False


def _elapsed_ms_since(created_at: object) -> float | None:
    if not created_at:
        return None
    try:
        created = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        return None
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - created).total_seconds() * 1000)


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
            body = message["body"]
            note_id = body.get("note_id")
            created_at = body.get("created_at")
            queue_ms = _elapsed_ms_since(created_at)
            started = time.perf_counter()
            try:
                result = process_sqs_message(body)
                duration_ms = round((time.perf_counter() - started) * 1000, 1)
                end_to_end_ms = _elapsed_ms_since(created_at)
                log_timing_event(
                    "note_processing",
                    message_id=message["message_id"],
                    note_id=note_id,
                    duration_ms=duration_ms,
                    queue_ms=None if queue_ms is None else round(queue_ms, 1),
                    end_to_end_ms=(
                        None if end_to_end_ms is None else round(end_to_end_ms, 1)
                    ),
                    success=True,
                )
                logger.info("Processed message %s: %s", message["message_id"], result)
                if not delete_sqs_message(message["receipt_handle"]):
                    logger.warning(
                        "Processed message %s but failed to delete it; it may be redelivered",
                        message["message_id"],
                    )
            except Exception as exc:
                duration_ms = round((time.perf_counter() - started) * 1000, 1)
                log_timing_event(
                    "note_processing_failed",
                    message_id=message["message_id"],
                    note_id=note_id,
                    duration_ms=duration_ms,
                    queue_ms=None if queue_ms is None else round(queue_ms, 1),
                    success=False,
                    error_type=type(exc).__name__,
                )
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
