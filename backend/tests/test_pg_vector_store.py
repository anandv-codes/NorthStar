"""Tests for the pgvector store's RPC mapping and chunk writes."""
from backend.app.infrastructure.vector.pg_vector_store import (
    PgVectorStore,
    replace_note_chunks,
)


class _Response:
    def __init__(self, data):
        self.data = data


def _store(rows, captured):
    def rpc(name, params):
        captured["name"] = name
        captured["params"] = params
        return _Response(rows)

    return PgVectorStore(rpc=rpc)


def test_query_related_notes_aggregates_chunks_to_best_per_note():
    captured = {}
    rows = [
        {"note_id": "n1", "content": "chunk a", "summary": "s1", "distance": 0.4},
        {"note_id": "n1", "content": "chunk b", "summary": "s1", "distance": 0.1},
        {"note_id": "n2", "content": "chunk c", "summary": "s2", "distance": 0.2},
    ]
    store = _store(rows, captured)

    results = store.query_related_notes("user-1", [0.1, 0.2], k=2)

    assert captured["name"] == "match_note_chunks"
    assert captured["params"]["match_user_id"] == "user-1"
    assert [note["note_id"] for note in results] == ["n1", "n2"]
    assert results[0]["distance"] == 0.1
    assert results[0]["text"] == "chunk b"


def test_query_related_notes_passes_exclude_and_respects_k():
    captured = {}
    rows = [{"note_id": f"n{i}", "content": "c", "distance": i / 10} for i in range(10)]
    store = _store(rows, captured)

    results = store.query_related_notes("user-1", [0.0], k=3, exclude_note_id="n0")

    assert captured["params"]["exclude_note_id"] == "n0"
    assert len(results) == 3


class _FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.op = None
        self.payload = None
        self.filters = []

    def delete(self):
        self.op = "delete"
        return self

    def insert(self, rows):
        self.op = "insert"
        self.payload = rows
        return self

    def update(self, payload):
        self.op = "update"
        self.payload = payload
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def execute(self):
        self.client.calls.append((self.table, self.op, self.payload, list(self.filters)))
        return _Response([])


class _FakeSupabase:
    def __init__(self):
        self.calls = []

    def table(self, name):
        return _FakeQuery(self, name)


def test_replace_note_chunks_deletes_then_inserts():
    client = _FakeSupabase()
    written = replace_note_chunks(
        "user-1",
        "note-1",
        [
            {"chunk_index": 0, "content": "a", "embedding": [0.1]},
            {"chunk_index": 1, "content": "b", "embedding": [0.2]},
        ],
        supabase=client,
    )

    assert written == 2
    ops = [(table, op) for table, op, _, _ in client.calls]
    assert ops == [("note_chunks", "delete"), ("note_chunks", "insert")]
    delete_filters = client.calls[0][3]
    assert ("user_id", "user-1") in delete_filters
    assert ("note_id", "note-1") in delete_filters
    inserted = client.calls[1][2]
    assert [row["chunk_index"] for row in inserted] == [0, 1]


def test_replace_note_chunks_clears_existing_when_empty():
    client = _FakeSupabase()
    assert replace_note_chunks("user-1", "note-1", [], supabase=client) == 0
    assert [(table, op) for table, op, _, _ in client.calls] == [("note_chunks", "delete")]
