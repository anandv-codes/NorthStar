"""Atomic, replayable ingestion (phase 7).

The bug this guards: the fan-out used to be a dozen separate PostgREST calls,
so a redelivery between them duplicated every typed memory, and a crash after
the LLM call paid for the same extraction twice. `note_id` is now the stable
attempt key, the payload is stored before the fan-out, and one RPC writes it
all or replays what the first attempt wrote.
"""
from pathlib import Path

from backend.app.infrastructure.db import memory_repository

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
MIGRATION = SQL_DIR / "phase7_atomic_ingestion.sql"


# -- Migration guards ------------------------------------------------------


def test_migration_adds_payload_and_commit_marker():
    text = MIGRATION.read_text(encoding="utf-8").lower()
    assert "add column if not exists payload jsonb" in text
    assert "add column if not exists fanned_out boolean not null default false" in text


def test_migration_makes_note_id_the_attempt_key():
    text = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create unique index if not exists idx_extraction_runs_note_unique" in text
    assert "on extraction_runs(note_id)" in text


def test_migration_backfills_runs_that_already_fanned_out():
    text = MIGRATION.read_text(encoding="utf-8").lower()
    assert "set fanned_out = true" in text
    for table in ("tasks", "facts", "questions", "decisions", "concepts"):
        assert f"from {table}" in text


def test_begin_extraction_run_reuses_the_existing_row():
    text = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create or replace function begin_extraction_run" in text
    assert "on conflict (note_id) do update" in text


def test_ingest_rpc_is_one_locked_transaction():
    text = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create or replace function ingest_note_memories" in text
    # The lock serialises concurrent deliveries; fanned_out is the commit
    # marker that turns the second delivery into a replay.
    assert "for update" in text
    assert "if v_fanned_out then" in text
    assert "update extraction_runs" in text


def test_ingest_rpc_writes_every_typed_table_and_links():
    text = MIGRATION.read_text(encoding="utf-8").lower()
    for table in (
        "insert into tasks",
        "insert into facts",
        "insert into questions",
        "insert into decisions",
        "insert into concepts",
        "insert into entities",
        "insert into memory_item_entities",
        "insert into commitment_contributions",
    ):
        assert table in text
    # Links and contributions de-duplicate instead of failing the retry.
    assert text.count("on conflict do nothing") >= 5
    assert "on conflict (commitment_id, note_id) do nothing" in text


def test_ingest_rpc_is_user_scoped():
    text = MIGRATION.read_text(encoding="utf-8").lower()
    assert "p_user_id" in text
    assert "where e.user_id = p_user_id" in text
    assert "and user_id = p_user_id" in text


def test_contributions_are_normalized_like_the_python_path():
    text = MIGRATION.read_text(encoding="utf-8").lower()
    assert "regexp_replace" in text
    assert "240" in text


# -- Repository wiring -----------------------------------------------------


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeRpc:
    def __init__(self, name, responses):
        self.name = name
        self.responses = responses

    def execute(self):
        return _FakeResponse(self.responses.get(self.name))


class _FakeTable:
    def __init__(self, name, calls):
        self.name = name
        self.calls = calls

    def update(self, values):
        self.calls["update"] = (self.name, values)
        return self

    def eq(self, column, value):
        self.calls["eq"] = (column, value)
        return self

    def execute(self):
        return _FakeResponse([])


class _FakeSupabase:
    def __init__(self, responses):
        self.responses = responses
        self.calls: dict = {}

    def rpc(self, name, params):
        self.calls[name] = params
        return _FakeRpc(name, self.responses)

    def table(self, name):
        return _FakeTable(name, self.calls)


def test_begin_extraction_run_calls_the_rpc_with_the_attempt_key(monkeypatch):
    fake = _FakeSupabase(
        {"begin_extraction_run": {"extraction_run_id": "run-1", "payload": None}}
    )
    monkeypatch.setattr(memory_repository, "supabase", fake)

    row = memory_repository.SupabaseMemoryRepository().begin_extraction_run(
        "user-1", "note-1", "gemini", "phase3-v1"
    )

    assert row["extraction_run_id"] == "run-1"
    params = fake.calls["begin_extraction_run"]
    assert params["p_user_id"] == "user-1"
    assert params["p_note_id"] == "note-1"
    assert params["p_model_name"] == "gemini"


def test_ingest_note_memories_calls_the_rpc(monkeypatch):
    fake = _FakeSupabase(
        {"ingest_note_memories": {"duplicate": False, "tasks": []}}
    )
    monkeypatch.setattr(memory_repository, "supabase", fake)

    result = memory_repository.SupabaseMemoryRepository().ingest_note_memories(
        "user-1", "note-1", "run-1", {"tasks": []}
    )

    assert result["duplicate"] is False
    params = fake.calls["ingest_note_memories"]
    assert params["p_extraction_run_id"] == "run-1"
    assert params["p_payload"] == {"tasks": []}


def test_save_extraction_payload_updates_the_run(monkeypatch):
    fake = _FakeSupabase({})
    monkeypatch.setattr(memory_repository, "supabase", fake)

    memory_repository.SupabaseMemoryRepository().save_extraction_payload(
        "run-1", {"summary": "s"}
    )

    table, values = fake.calls["update"]
    assert table == "extraction_runs"
    assert values == {"payload": {"summary": "s"}}
    assert fake.calls["eq"] == ("extraction_run_id", "run-1")
