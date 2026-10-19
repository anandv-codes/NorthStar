-- Phase 4 (PR4): pgvector-backed retrieval.
-- Run in the Supabase SQL editor AFTER phase4_recall.sql.
-- Idempotent: safe to re-run.
--
-- Replaces the local on-disk Chroma index as the runtime vector store. Note
-- text is chunked (see infrastructure/vector/chunking.py) and each chunk is
-- embedded; matching is user-scoped via the functions at the bottom.
--
-- DIMENSION: 768 matches the configured Gemini embedding output
-- (EMBEDDING_DIMENSIONS=768). If you change the embedding model/dimension,
-- update every `vector(768)` below AND re-embed all rows.

create extension if not exists vector;

-- ---------------------------------------------------------------------------
-- note_chunks: paragraph/sentence-level embeddings for retrieval
-- ---------------------------------------------------------------------------
create table if not exists note_chunks (
  chunk_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  note_id text not null references notes(note_id) on delete cascade,
  chunk_index integer not null,
  content text not null,
  token_count integer,
  embedding vector(768),
  created_at timestamptz not null default now(),
  unique (note_id, chunk_index)
);

create index if not exists idx_note_chunks_user_note
  on note_chunks(user_id, note_id);

-- HNSW gives good recall without a training step (unlike ivfflat) and is the
-- right default for small/medium corpora.
create index if not exists idx_note_chunks_embedding_hnsw
  on note_chunks using hnsw (embedding vector_cosine_ops);

-- ---------------------------------------------------------------------------
-- Note-level embeddings (optional aggregate, used for note-level matching)
-- ---------------------------------------------------------------------------
alter table notes
  add column if not exists embedding vector(768);

-- ---------------------------------------------------------------------------
-- Entity embeddings (concept consolidation, PR5)
-- ---------------------------------------------------------------------------
alter table entities
  add column if not exists embedding vector(768);

create index if not exists idx_entities_embedding_hnsw
  on entities using hnsw (embedding vector_cosine_ops);

-- ---------------------------------------------------------------------------
-- Matching RPCs (user-scoped, cosine distance)
-- ---------------------------------------------------------------------------
create or replace function match_note_chunks(
  query_embedding vector(768),
  match_user_id text,
  match_count integer default 5,
  exclude_note_id text default null
)
returns table (
  chunk_id uuid,
  note_id text,
  content text,
  summary text,
  distance float
)
language sql
stable
as $$
  select
    c.chunk_id,
    c.note_id,
    c.content,
    n.enriched_summary as summary,
    (c.embedding <=> query_embedding) as distance
  from note_chunks c
  join notes n on n.note_id = c.note_id
  where c.user_id = match_user_id
    and c.embedding is not null
    and (exclude_note_id is null or c.note_id <> exclude_note_id)
  order by c.embedding <=> query_embedding
  limit greatest(1, match_count);
$$;

create or replace function match_notes(
  query_embedding vector(768),
  match_user_id text,
  match_count integer default 5,
  exclude_note_id text default null
)
returns table (
  note_id text,
  content text,
  summary text,
  distance float
)
language sql
stable
as $$
  select
    n.note_id,
    n.raw_text as content,
    n.enriched_summary as summary,
    (n.embedding <=> query_embedding) as distance
  from notes n
  where n.user_id = match_user_id
    and n.embedding is not null
    and (exclude_note_id is null or n.note_id <> exclude_note_id)
  order by n.embedding <=> query_embedding
  limit greatest(1, match_count);
$$;

create or replace function match_entities(
  query_embedding vector(768),
  match_user_id text,
  match_count integer default 5
)
returns table (
  entity_id uuid,
  name text,
  entity_type text,
  distance float
)
language sql
stable
as $$
  select
    e.entity_id,
    e.name,
    e.entity_type,
    (e.embedding <=> query_embedding) as distance
  from entities e
  where e.user_id = match_user_id
    and e.embedding is not null
  order by e.embedding <=> query_embedding
  limit greatest(1, match_count);
$$;
