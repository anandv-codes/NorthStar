"""Natural keys for typed memories (phase 8).

Phase 7 makes a redelivery safe; these constraints make duplication impossible
even if a future caller forgets the guard. The key is
`(source_note_id, extraction_run_id, content_hash)`, where the hash normalizes
case and surrounding whitespace.
"""
from pathlib import Path

import pytest

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
MIGRATION = SQL_DIR / "phase8_typed_memory_keys.sql"

TYPED = {
    "tasks": ("task_id", "description"),
    "facts": ("fact_id", "content"),
    "questions": ("question_id", "question"),
    "decisions": ("decision_id", "decision"),
    "concepts": ("concept_id", "concept"),
}


def _text() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


@pytest.mark.parametrize("table", TYPED)
def test_every_typed_table_gets_a_content_hash(table: str):
    text = _text()
    assert f"alter table {table}" in text
    assert "add column if not exists content_hash text" in text
    assert f"idx_{table}_note_run_content" in text


@pytest.mark.parametrize("table", TYPED)
def test_every_typed_table_gets_the_natural_key_index(table: str):
    text = _text()
    assert (
        f"on {table}(source_note_id, extraction_run_id, content_hash)" in text
    )


def test_hash_normalizes_case_and_whitespace():
    text = _text()
    # Backfill and fan-out must use the same expression, or the index and the
    # RPC disagree about what "the same memory" means.
    assert text.count("md5(lower(btrim(") >= 10


@pytest.mark.parametrize(
    "table,column", [(table, cols[1]) for table, cols in TYPED.items()]
)
def test_backfill_hashes_the_right_column(table: str, column: str):
    text = _text()
    assert f"update {table}\n   set content_hash = md5(lower(btrim({column})))" in text


def test_rpc_resolves_a_duplicate_instead_of_aborting():
    text = _text()
    # A duplicate item inside one payload must reuse the existing row id, not
    # raise and turn the note into a poison message.
    assert text.count("on conflict (source_note_id, extraction_run_id, content_hash) do update") == 5
    assert text.count("returning task_id into v_row_id") == 1
    assert "set description = tasks.description" in text


@pytest.mark.parametrize(
    "table,column", [(table, cols[1]) for table, cols in TYPED.items()]
)
def test_rpc_hashes_the_right_column(table: str, column: str):
    text = _text()
    assert f"md5(lower(btrim(coalesce(v_item->>'{column}', ''))))" in text


def test_migration_notes_that_phase7_already_covers_the_active_run():
    text = _text()
    assert "extraction_runs(note_id)" in text
    assert "phase 7" in text
