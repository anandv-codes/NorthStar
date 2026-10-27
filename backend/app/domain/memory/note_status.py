"""The note lifecycle.

``processing``  the job is running; nothing user-visible exists yet.
``enriched``    the LLM extraction and typed memories are persisted, but the
                note is not retrievable yet (vector indexing has not finished).
``indexed``     the only success terminal state: typed memories *and* vectors
                are in place, so retrieval can find the note.
``failed``      a terminal failure; ``index_error`` carries the reason.

``enriched`` deliberately sits between extraction and indexing. It used to be
reported as ``completed`` before ``index_note`` ran, which meant a note could
look done while being invisible to retrieval.
"""
from __future__ import annotations

NOTE_STATUSES = ("processing", "enriched", "indexed", "failed")

NOTE_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "processing": {"enriched", "failed"},
    "enriched": {"indexed", "failed"},
    "indexed": set(),
    # A retry (SQS redelivery, manual reprocess) re-enters the lifecycle.
    "failed": {"processing"},
}


class InvalidNoteStatusTransition(ValueError):
    """Raised when a write would move a note to an impossible state."""


def validate_note_status_transition(current: str, next_status: str) -> None:
    """Raise unless ``current -> next_status`` is a legal note transition.

    Idempotent writes (``current == next_status``) are allowed so a retried
    job does not fail on a state it already reached.
    """
    if current == next_status:
        return

    allowed = NOTE_STATUS_TRANSITIONS.get(current)
    if allowed is None:
        raise InvalidNoteStatusTransition(f"Unknown note status: {current}")
    if next_status not in allowed:
        raise InvalidNoteStatusTransition(
            f"Invalid note status transition: {current} -> {next_status}"
        )
