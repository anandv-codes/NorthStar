"""Static guards for the idempotent SQL migrations.

The README tells users to re-run these files on existing databases, so every
DDL statement must be idempotent. These tests do not need a database.
"""
import re
from pathlib import Path

import pytest

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
SQL_FILES = sorted(SQL_DIR.glob("*.sql"))

CREATE_RE = re.compile(r"create\s+(unique\s+)?(table|index)\s+(?!if\s+not\s+exists)", re.I)
ADD_COLUMN_RE = re.compile(r"alter\s+table\s+\w+\s+add\s+column\s+(?!if\s+not\s+exists)", re.I)

RECALL_TABLES = [
    "note_entities",
    "commitments",
    "recall_candidates",
    "recall_cards",
    "review_history",
]


@pytest.mark.parametrize("sql_file", SQL_FILES, ids=lambda p: p.name)
def test_create_statements_are_idempotent(sql_file: Path):
    text = sql_file.read_text(encoding="utf-8")
    assert not CREATE_RE.search(text), (
        f"{sql_file.name} has a create table/index without `if not exists`"
    )


@pytest.mark.parametrize("sql_file", SQL_FILES, ids=lambda p: p.name)
def test_add_column_statements_are_idempotent(sql_file: Path):
    text = sql_file.read_text(encoding="utf-8")
    assert not ADD_COLUMN_RE.search(text), (
        f"{sql_file.name} has `add column` without `if not exists`"
    )


def test_recall_migration_defines_expected_tables():
    text = (SQL_DIR / "phase4_recall.sql").read_text(encoding="utf-8").lower()
    for table in RECALL_TABLES:
        assert f"create table if not exists {table}" in text


def test_recall_migration_adds_scoring_and_due_date_columns():
    text = (SQL_DIR / "phase4_recall.sql").read_text(encoding="utf-8").lower()
    for column in ("importance", "mention_count", "due_date", "durability", "next_due", "easiness"):
        assert column in text


def test_recall_migration_adds_note_toggle_and_candidate_text():
    text = (SQL_DIR / "phase4_recall.sql").read_text(encoding="utf-8").lower()
    assert "recall_enabled" in text
    assert "recall_status" in text
    # Must be an explicit ALTER, not only a column in the create-table body.
    assert "add column if not exists text text" in text


def test_decks_migration_adds_deck_table_and_references():
    text = (SQL_DIR / "phase4_recall_decks.sql").read_text(encoding="utf-8").lower()
    assert "create table if not exists recall_decks" in text
    assert "add column if not exists deck_id" in text
    assert "is_default" in text
    assert "update recall_cards" in text
    assert "update recall_candidates" in text


def test_scheduler_migration_adds_state_and_learning_step():
    text = (SQL_DIR / "phase4_recall_scheduler.sql").read_text(encoding="utf-8").lower()
    assert "add column if not exists state" in text
    assert "add column if not exists learning_step" in text


def test_accept_rpc_is_idempotent_and_user_scoped():
    text = (SQL_DIR / "phase4_recall_accept.sql").read_text(encoding="utf-8").lower()
    assert "create or replace function accept_recall_candidate" in text
    assert "p_user_id" in text
    assert "for update" in text
    assert "insert into recall_cards" in text
    # A retry must return the existing card rather than hitting the unique index.
    assert "from recall_cards" in text
    assert "'carded'" in text


def test_pgvector_migration_defines_chunks_indexes_and_match_functions():
    text = (SQL_DIR / "phase4_pgvector.sql").read_text(encoding="utf-8").lower()
    assert "create extension if not exists vector" in text
    assert "create table if not exists note_chunks" in text
    assert "using hnsw" in text
    for function in ("match_note_chunks", "match_notes", "match_entities"):
        assert f"create or replace function {function}" in text


def test_commitments_migration_defines_user_goals_and_contributions():
    text = (SQL_DIR / "phase5_commitments.sql").read_text(encoding="utf-8").lower()
    assert "create table if not exists user_commitments" in text
    assert "create table if not exists commitment_contributions" in text
    assert "progress between 0 and 100" in text
    assert "status in ('active', 'completed')" in text
    assert "unique index if not exists idx_commitment_contributions_commitment_note" in text
    assert "on delete cascade" in text


def test_match_functions_are_user_scoped():
    text = (SQL_DIR / "phase4_pgvector.sql").read_text(encoding="utf-8").lower()
    assert text.count("match_user_id") >= 6


def test_apply_script_runs_every_migration():
    """A migration that the script skips silently leaves the schema incomplete."""
    script = (Path(__file__).resolve().parents[1] / "scripts" / "apply_migrations.sh").read_text(
        encoding="utf-8"
    )
    listed = set(re.findall(r"[\w-]+\.sql", script))
    expected = {path.name for path in SQL_FILES}
    assert expected <= listed, f"apply_migrations.sh is missing: {sorted(expected - listed)}"
