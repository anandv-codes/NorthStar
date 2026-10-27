# Database migrations

All migrations target the **Supabase Postgres** database (the app talks to it
through the Supabase client / PostgREST). They are idempotent, so re-running a
file is safe.

## Order

Apply in this exact order on a fresh database:

| # | File | Adds |
|---|------|------|
| 1 | `auth_jwt.sql` | `users`, `refresh_tokens` (JWT auth) |
| 2 | `chat_conversations.sql` | `chat_threads`, `chat_messages`, `pending_chat_actions` |
| 3 | `phase3_work_memory.sql` | `notes`, `entities`, tasks/facts/questions/decisions/concepts, extraction runs, summaries, and the legacy dormant `risks` table |
| 4 | `phase4_recall.sql` | per-note recall opt-in, `note_entities`, `commitments`, `recall_candidates`, `recall_cards`, `review_history` |
| 5 | `phase4_recall_scheduler.sql` | Anki scheduler columns (`state`, `learning_step`) on `recall_cards` |
| 6 | `phase4_recall_decks.sql` | `recall_decks`, `deck_id` on candidates/cards, General deck backfill |
| 7 | `phase4_recall_accept.sql` | `accept_recall_candidate` RPC: atomic, idempotent accept |
| 8 | `phase4_pgvector.sql` | `vector` extension, `note_chunks`, embedding columns, `match_*` RPCs |
| 9 | `phase5_commitments.sql` | `user_commitments`, `commitment_contributions` (user-authored long-term goals) |
| 10 | `phase6_note_status.sql` | one note-status vocabulary (`processing`/`enriched`/`indexed`/`failed`), `indexed_at`, `index_error`, and a `CHECK` constraint |
| 11 | `phase7_atomic_ingestion.sql` | `extraction_runs.payload`/`fanned_out`, one run per note, and the `begin_extraction_run` + `ingest_note_memories` RPCs |
| 12 | `phase8_typed_memory_keys.sql` | `content_hash` on typed memories, unique `(source_note_id, extraction_run_id, content_hash)`, and the conflict-safe fan-out |

## Option A — Supabase SQL editor

Open each file in order and run it. Before step 8, enable the **vector**
extension in the Supabase dashboard (Database → Extensions) if
`create extension if not exists vector;` is rejected; then run the file.

## Option B — `psql` (scripted)

Use the **direct/session** connection string from Supabase
(Project Settings → Database → Connection string → URI). Supabase's
transaction pooler on port `6543` does not support every DDL statement.

```bash
export SUPABASE_DB_URL='postgresql://postgres:<password>@db.<project>.supabase.co:5432/postgres'
./backend/scripts/apply_migrations.sh
```

The script stops on the first error (`ON_ERROR_STOP=1`) and prints the file it
was applying.

## After migrating a pre-existing corpus

New notes embed automatically, but notes created before `phase4_pgvector.sql`
have no chunks. Backfill once (safe to re-run):

```bash
cd /opt/northstar
.venv/bin/python -m backend.scripts.backfill_pgvector
# or scope it:
.venv/bin/python -m backend.scripts.backfill_pgvector --user-id <user_id>
# dry run:
.venv/bin/python -m backend.scripts.backfill_pgvector --dry-run
```

`EMBEDDING_DIMENSIONS` must stay at `768` to match the `vector(768)` columns;
changing the embedding model/dimension requires editing the migration and
re-embedding every note.
