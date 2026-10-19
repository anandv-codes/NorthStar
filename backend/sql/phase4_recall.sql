-- Phase 4 (PR2): recall foundation.
-- Run in the Supabase SQL editor AFTER phase3_work_memory.sql.
-- Every statement is idempotent (`if not exists` / guarded backfills) so this
-- file is safe to re-run on an existing database.
--
-- Adds the recall loop's persistent state:
--   note_entities      note <-> entity links (many-to-many) with context snippet
--   entities.*         importance / mention_count / updated_at for consolidation
--   tasks.*            due_date / importance / durability for commitments
--   commitments        confirmable commitments extracted from notes (Act stage)
--   recall_candidates  scored knowledge units moving through a review lifecycle
--   recall_cards       accepted flash cards + Anki-style scheduling state
--   review_history     per-review provenance for analytics
-- Embeddings / chunks / pgvector live in phase4_pgvector.sql (PR4).

-- ---------------------------------------------------------------------------
-- Notes: per-note opt-in for recall question generation
-- Candidates are still scored for every note, but questions (the only LLM
-- cost in the recall loop) are generated only when this flag is true. Toggling
-- it ON later generates questions for already-scored candidates.
-- ---------------------------------------------------------------------------
alter table notes
  add column if not exists recall_enabled boolean not null default false,
  add column if not exists recall_status text not null default 'off';

-- ---------------------------------------------------------------------------
-- Entities: evolving importance + mention tracking
-- ---------------------------------------------------------------------------
alter table entities
  add column if not exists importance numeric not null default 0,
  add column if not exists mention_count integer not null default 1,
  add column if not exists updated_at timestamptz;

update entities
  set updated_at = created_at
  where updated_at is null;

alter table entities
  alter column updated_at set default now();

create index if not exists idx_entities_user_importance
  on entities(user_id, importance desc);

-- ---------------------------------------------------------------------------
-- note_entities: explicit note <-> entity join for recall provenance
-- ---------------------------------------------------------------------------
create table if not exists note_entities (
  user_id text not null,
  note_id text not null references notes(note_id),
  entity_id uuid not null references entities(entity_id),
  snippet text,
  created_at timestamptz not null default now(),
  primary key (note_id, entity_id)
);

create index if not exists idx_note_entities_user_entity
  on note_entities(user_id, entity_id);

create index if not exists idx_note_entities_note_id
  on note_entities(note_id);

-- ---------------------------------------------------------------------------
-- Tasks: due dates + recall scoring inputs
-- ---------------------------------------------------------------------------
alter table tasks
  add column if not exists due_date date,
  add column if not exists importance numeric,
  add column if not exists durability numeric;

create index if not exists idx_tasks_user_due_date
  on tasks(user_id, due_date)
  where status = 'open' and due_date is not null;

-- ---------------------------------------------------------------------------
-- Commitments: the Act-stage bridge between a note and calendar action
-- ---------------------------------------------------------------------------
create table if not exists commitments (
  commitment_id uuid primary key,
  user_id text not null,
  source_note_id text not null references notes(note_id),
  task_id uuid references tasks(task_id),
  title text not null,
  due_date date,
  status text not null default 'pending',
  confidence numeric,
  calendar_provider text,
  calendar_event_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  confirmed_at timestamptz
);

create index if not exists idx_commitments_user_status_due
  on commitments(user_id, status, due_date);

create index if not exists idx_commitments_source_note_id
  on commitments(source_note_id);

-- ---------------------------------------------------------------------------
-- recall_candidates: scored knowledge units and their review lifecycle
-- State machine: new -> candidate -> (suggested -> approved | rejected) -> carded
-- ---------------------------------------------------------------------------
create table if not exists recall_candidates (
  candidate_id uuid primary key,
  user_id text not null,
  item_type text not null,
  item_id uuid,
  source_note_id text references notes(note_id),
  text text,
  prompt text,
  answer text,
  importance numeric,
  durability numeric,
  mention_count integer not null default 1,
  related_note_count integer not null default 1,
  recency_score numeric,
  user_interest_score numeric,
  score numeric,
  status text not null default 'new',
  dedupe_key text,
  rationale jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  decided_at timestamptz
);

create index if not exists idx_recall_candidates_user_status_score
  on recall_candidates(user_id, status, score desc);

create index if not exists idx_recall_candidates_user_item
  on recall_candidates(user_id, item_type, item_id);

create index if not exists idx_recall_candidates_source_note_id
  on recall_candidates(source_note_id);

-- Existing databases created recall_candidates before `text` existed; the
-- create-table above is a no-op there, so add the column explicitly.
alter table recall_candidates
  add column if not exists text text;

-- Not partial: PostgREST upsert can only target a full unique index. Postgres
-- treats NULLs as distinct, so candidates without a dedupe_key never collide.
create unique index if not exists idx_recall_candidates_user_dedupe
  on recall_candidates(user_id, dedupe_key);

-- ---------------------------------------------------------------------------
-- recall_cards: approved flash cards + SM-2 scheduling state
-- ---------------------------------------------------------------------------
create table if not exists recall_cards (
  card_id uuid primary key,
  user_id text not null,
  candidate_id uuid references recall_candidates(candidate_id),
  question text not null,
  answer text not null,
  source_note_ids text[] not null default '{}',
  entity_ids uuid[] not null default '{}',
  status text not null default 'active',
  state text not null default 'new',
  learning_step integer not null default 0,
  interval integer not null default 0,
  easiness numeric not null default 2.5,
  repetitions integer not null default 0,
  lapses integer not null default 0,
  review_count integer not null default 0,
  last_reviewed timestamptz,
  next_due timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_recall_cards_user_status_due
  on recall_cards(user_id, status, next_due);

create index if not exists idx_recall_cards_user_created_at
  on recall_cards(user_id, created_at desc);

create unique index if not exists idx_recall_cards_user_candidate
  on recall_cards(user_id, candidate_id)
  where candidate_id is not null;

-- ---------------------------------------------------------------------------
-- review_history: immutable per-review provenance
-- ---------------------------------------------------------------------------
create table if not exists review_history (
  review_id uuid primary key,
  user_id text not null,
  card_id uuid not null references recall_cards(card_id),
  reviewed_at timestamptz not null default now(),
  grade smallint not null check (grade between 1 and 5),
  previous_interval integer,
  new_interval integer,
  previous_easiness numeric,
  new_easiness numeric,
  elapsed_ms integer
);

create index if not exists idx_review_history_card_reviewed
  on review_history(card_id, reviewed_at desc);

create index if not exists idx_review_history_user_reviewed
  on review_history(user_id, reviewed_at desc);

-- ---------------------------------------------------------------------------
-- Entity consolidation: bump mention_count/importance for recurring names.
-- Called after upsert_entities (PR5) so entities seen across many notes gain
-- weight over time. Name matching is case-insensitive on the stored name.
-- ---------------------------------------------------------------------------
create or replace function bump_entity_mentions(
  match_user_id text,
  entity_names text[],
  importance_delta numeric default 0.1
)
returns void
language sql
as $$
  update entities
  set mention_count = mention_count + 1,
      importance = least(1.0, importance + importance_delta),
      updated_at = now()
  where user_id = match_user_id
    and lower(name) = any (select lower(unnest(entity_names)));
$$;
