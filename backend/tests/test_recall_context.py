"""Tests for rehydrating multi-note context during on-demand answer generation."""
from backend.app.domain.recall.question_service import collect_related_context


def test_collect_related_context_rehydrates_related_snippets():
    note = {
        "note_id": "note-1",
        "context_note_ids": ["note-1", "note-2", "note-3", "note-4"],
    }
    notes = {
        "note-2": {"enriched_summary": "After five attempts the message is dead-lettered."},
        "note-3": {"raw_text": "The worker fleet drains the retry queue."},
    }
    calls: list[str] = []

    def load_note(note_id):
        calls.append(note_id)
        return notes.get(note_id, {})

    snippets, related_note_ids = collect_related_context(note, load_note)

    assert snippets == [
        "After five attempts the message is dead-lettered.",
        "The worker fleet drains the retry queue.",
    ]
    assert related_note_ids == ["note-2", "note-3"]
    assert calls == ["note-2", "note-3"]


def test_collect_related_context_skips_unavailable_related_notes():
    note = {"note_id": "note-1", "context_note_ids": ["note-2", "note-3"]}
    notes = {"note-3": {"raw_text": "The worker fleet drains the retry queue."}}

    snippets, related_note_ids = collect_related_context(
        note, lambda note_id: notes.get(note_id, {})
    )

    assert snippets == ["The worker fleet drains the retry queue."]
    assert related_note_ids == ["note-3"]


def test_collect_related_context_ignores_the_source_note_itself():
    note = {"note_id": "note-1", "context_note_ids": ["note-1"]}

    def unexpected(note_id):
        raise AssertionError("the source note must not be loaded as related context")

    assert collect_related_context(note, unexpected) == ([], [])


def test_collect_related_context_without_context_ids_is_empty():
    assert collect_related_context({"note_id": "note-1"}, lambda note_id: {}) == ([], [])
