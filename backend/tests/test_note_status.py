"""The note lifecycle: transitions, terminal states, and the migration.

The bug this guards: `completed` used to be written *before* `index_note` ran,
and indexing errors were swallowed. A note could therefore look finished while
being invisible to retrieval. `indexed` is now the only success terminal state,
and an indexing failure is recorded as `failed` with a reason.
"""
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.domain.memory.note_status import (
    NOTE_STATUSES,
    InvalidNoteStatusTransition,
    validate_note_status_transition,
)
from backend.app.schemas.models import NoteStatusResponse
from backend.app.workers import note_processor

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
MIGRATION = SQL_DIR / "phase6_note_status.sql"


# -- State machine ---------------------------------------------------------


@pytest.mark.parametrize(
    "current,next_status",
    [
        ("processing", "enriched"),
        ("processing", "failed"),
        ("enriched", "indexed"),
        ("enriched", "failed"),
        ("failed", "processing"),
    ],
)
def test_allowed_transitions(current: str, next_status: str):
    validate_note_status_transition(current, next_status)


@pytest.mark.parametrize(
    "current,next_status",
    [
        ("processing", "indexed"),  # cannot skip extraction
        ("indexed", "processing"),  # terminal success
        ("indexed", "failed"),
        ("failed", "enriched"),  # retries re-enter via processing
        ("completed", "indexed"),  # retired vocabulary
    ],
)
def test_rejected_transitions(current: str, next_status: str):
    with pytest.raises(InvalidNoteStatusTransition):
        validate_note_status_transition(current, next_status)


def test_idempotent_write_is_allowed():
    validate_note_status_transition("indexed", "indexed")


def test_vocabulary_has_exactly_four_states():
    assert NOTE_STATUSES == ("processing", "enriched", "indexed", "failed")


# -- API schema ------------------------------------------------------------


def _note_payload(status: str) -> dict:
    return {
        "note_id": "note-1",
        "user_id": "user-1",
        "status": status,
        "created_at": datetime.now(timezone.utc),
        "raw_text": "text",
    }


def test_response_rejects_retired_completed_status():
    with pytest.raises(ValidationError):
        NoteStatusResponse(**_note_payload("completed"))


def test_response_accepts_indexed_with_timestamp():
    payload = _note_payload("indexed")
    payload["indexed_at"] = datetime.now(timezone.utc)
    assert NoteStatusResponse(**payload).status == "indexed"


# -- Pipeline behaviour ----------------------------------------------------


class _FakeCommitmentRepo:
    def query_commitments(self, user_id, status=None):
        return []


def _patch_pipeline(
    monkeypatch,
    *,
    stored_payload: dict | None = None,
    calls: dict | None = None,
) -> list[dict]:
    """Replace every external call in `process_sqs_message` with a no-op."""
    updates: list[dict] = []
    calls = calls if calls is not None else {}

    def record_update(user_id, note_id, payload):
        updates.append(dict(payload))
        return payload

    monkeypatch.setattr(
        note_processor,
        "get_note_item",
        lambda *a, **k: {"status": "processing", "recall_enabled": False},
    )
    monkeypatch.setattr(note_processor, "update_note_item", record_update)
    monkeypatch.setattr(
        note_processor,
        "fetch_note_context",
        lambda *a, **k: {"related_notes": [], "retrieval_sources": {}},
    )
    monkeypatch.setattr(
        note_processor, "get_commitment_repository", lambda: _FakeCommitmentRepo()
    )

    def fake_llm(*a, **k):
        calls["llm"] = calls.get("llm", 0) + 1
        return {
            "summary": "summary",
            "tasks": [],
            "facts": [],
            "questions": [],
            "decisions": [],
            "concepts": [],
            "entities": [],
        }

    monkeypatch.setattr(note_processor, "call_gemini_api", fake_llm)
    monkeypatch.setattr(
        note_processor,
        "begin_extraction_run",
        lambda *a, **k: {
            "extraction_run_id": "run-1",
            "payload": stored_payload,
            "fanned_out": bool(stored_payload),
        },
    )

    def fake_save(run_id, payload):
        calls["saved"] = calls.get("saved", 0) + 1

    monkeypatch.setattr(note_processor, "save_extraction_payload", fake_save)

    def fake_ingest(*a, **k):
        calls["ingest"] = calls.get("ingest", 0) + 1
        return {
            "duplicate": False,
            "tasks": [],
            "facts": [],
            "questions": [],
            "decisions": [],
            "concepts": [],
            "entities": [],
            "links": 0,
            "contributions": 0,
        }

    monkeypatch.setattr(note_processor, "ingest_note_memories", fake_ingest)
    monkeypatch.setattr(note_processor, "build_note_metadata", lambda *a, **k: {})
    monkeypatch.setattr(note_processor, "task_rows_with_scoring", lambda *a, **k: [])
    monkeypatch.setattr(note_processor, "generate_candidates", lambda *a, **k: [])
    monkeypatch.setattr(note_processor, "bump_entity_mentions", lambda *a, **k: None)
    monkeypatch.setattr(note_processor, "entity_importance_delta", lambda *a, **k: 0.1)
    monkeypatch.setattr(note_processor, "get_chat_model", lambda: object())
    monkeypatch.setattr(note_processor, "get_recall_repository", lambda: object())
    monkeypatch.setattr(note_processor, "build_context", lambda *a, **k: "")
    monkeypatch.setattr(note_processor, "generate_questions", lambda *a, **k: [])
    monkeypatch.setattr(
        note_processor,
        "apply_deterministic_task_resolution",
        lambda *a, **k: {"updated_tasks": []},
    )
    monkeypatch.setattr(
        note_processor, "append_deterministic_resolution_log", lambda *a, **k: None
    )
    return updates


def _run(monkeypatch, index_behavior) -> tuple[dict, list[dict]]:
    updates = _patch_pipeline(monkeypatch)
    monkeypatch.setattr(note_processor, "index_note", index_behavior)
    result = note_processor.process_sqs_message(
        {"note_id": "note-1", "user_id": "user-1", "raw_text": "hello"}
    )
    return result, updates


def test_indexing_success_sets_indexed_after_index_note(monkeypatch):
    result, updates = _run(monkeypatch, lambda *a, **k: 3)

    statuses = [update.get("status") for update in updates if "status" in update]
    assert statuses == ["enriched", "indexed"]
    assert updates[-1]["indexed_at"]
    assert result == {"success": True, "note_id": "note-1", "status": "indexed"}


def test_indexing_failure_is_visible_not_swallowed(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("embedding provider timed out")

    result, updates = _run(monkeypatch, boom)

    assert updates[-1]["status"] == "failed"
    assert "embedding provider timed out" in updates[-1]["index_error"]
    assert result["status"] == "failed"
    assert result["success"] is False


# -- Idempotent ingestion --------------------------------------------------


def test_first_attempt_calls_llm_once_and_persists_payload(monkeypatch):
    calls: dict = {}
    _patch_pipeline(monkeypatch, calls=calls)
    monkeypatch.setattr(note_processor, "index_note", lambda *a, **k: 1)

    note_processor.process_sqs_message(
        {"note_id": "note-1", "user_id": "user-1", "raw_text": "hello"}
    )

    assert calls["llm"] == 1
    assert calls["saved"] == 1
    assert calls["ingest"] == 1


def test_redelivery_replays_stored_payload_without_calling_the_llm(monkeypatch):
    calls: dict = {}
    payload = {
        "summary": "cached",
        "tasks": [],
        "facts": [],
        "questions": [],
        "decisions": [],
        "concepts": [],
        "entities": [],
    }
    _patch_pipeline(monkeypatch, stored_payload=payload, calls=calls)
    monkeypatch.setattr(note_processor, "index_note", lambda *a, **k: 1)

    result = note_processor.process_sqs_message(
        {"note_id": "note-1", "user_id": "user-1", "raw_text": "hello"}
    )

    assert calls.get("llm", 0) == 0
    assert calls.get("saved", 0) == 0
    assert calls["ingest"] == 1
    assert result["status"] == "indexed"


def test_duplicate_delivery_of_indexed_note_is_a_noop(monkeypatch):
    calls: dict = {}
    updates = _patch_pipeline(monkeypatch, calls=calls)
    monkeypatch.setattr(
        note_processor,
        "get_note_item",
        lambda *a, **k: {"status": "indexed", "recall_enabled": False},
    )

    result = note_processor.process_sqs_message(
        {"note_id": "note-1", "user_id": "user-1", "raw_text": "hello"}
    )

    assert result == {"success": True, "note_id": "note-1", "status": "indexed"}
    assert updates == []
    assert calls.get("llm", 0) == 0


# -- Migration guards ------------------------------------------------------


def test_migration_adds_index_state_columns():
    text = MIGRATION.read_text(encoding="utf-8").lower()
    assert "add column if not exists indexed_at" in text
    assert "add column if not exists index_error" in text


def test_migration_backfills_legacy_completed_rows():
    text = MIGRATION.read_text(encoding="utf-8").lower()
    assert "set status = 'indexed'" in text
    assert "where status = 'completed'" in text


def test_migration_constrains_the_vocabulary():
    text = MIGRATION.read_text(encoding="utf-8").lower()
    assert "notes_status_check" in text
    for status in NOTE_STATUSES:
        assert f"'{status}'" in text
