-- Phase 3: AI Work Memory typed storage.
-- Run this in the Supabase SQL editor.
-- Supabase remains the source of truth; Chroma remains a derived semantic index.

alter table notes
  add column if not exists enriched_summary text,
  add column if not exists action_items jsonb,
  add column if not exists questions jsonb,
  add column if not exists insights jsonb,
  add column if not exists metadata jsonb,
  add column if not exists processed_at timestamptz;

-- Existing Phase 1 notes tables may have note_id as a plain column instead of
-- a primary/unique key. Referenced columns must be unique in Postgres.
create unique index if not exists idx_notes_note_id_unique
  on notes(note_id);

create table if not exists extraction_runs (
  extraction_run_id uuid primary key,
  note_id text not null references notes(note_id),
  user_id text not null,
  model_name text not null,
  prompt_version text not null,
  status text not null,
  error_message text,
  created_at timestamptz not null
);

create table if not exists tasks (
  task_id uuid primary key,
  user_id text not null,
  source_note_id text not null references notes(note_id),
  extraction_run_id uuid references extraction_runs(extraction_run_id),
  description text not null,
  status text not null default 'open',
  created_by text not null default 'llm',
  confidence numeric,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  completed_at timestamptz
);

create table if not exists facts (
  fact_id uuid primary key,
  user_id text not null,
  source_note_id text not null references notes(note_id),
  extraction_run_id uuid references extraction_runs(extraction_run_id),
  content text not null,
  created_by text not null default 'llm',
  confidence numeric,
  created_at timestamptz not null
);

create table if not exists questions (
  question_id uuid primary key,
  user_id text not null,
  source_note_id text not null references notes(note_id),
  extraction_run_id uuid references extraction_runs(extraction_run_id),
  question text not null,
  status text not null default 'open',
  answer text,
  created_by text not null default 'llm',
  confidence numeric,
  created_at timestamptz not null,
  resolved_at timestamptz
);

create table if not exists decisions (
  decision_id uuid primary key,
  user_id text not null,
  source_note_id text not null references notes(note_id),
  extraction_run_id uuid references extraction_runs(extraction_run_id),
  decision text not null,
  rationale text,
  created_by text not null default 'llm',
  confidence numeric,
  created_at timestamptz not null
);

create table if not exists risks (
  risk_id uuid primary key,
  user_id text not null,
  source_note_id text not null references notes(note_id),
  extraction_run_id uuid references extraction_runs(extraction_run_id),
  risk text not null,
  severity text,
  status text not null default 'open',
  created_by text not null default 'llm',
  confidence numeric,
  created_at timestamptz not null,
  resolved_at timestamptz
);

create table if not exists entities (
  entity_id uuid primary key,
  user_id text not null,
  name text not null,
  entity_type text,
  created_at timestamptz not null,
  unique(user_id, name)
);

create table if not exists memory_item_entities (
  user_id text not null,
  entity_id uuid not null references entities(entity_id),
  item_type text not null,
  item_id uuid not null,
  source_note_id text not null references notes(note_id),
  created_at timestamptz not null,
  primary key (user_id, entity_id, item_type, item_id)
);

create index if not exists idx_extraction_runs_note_id
  on extraction_runs(note_id);

create index if not exists idx_extraction_runs_user_created_at
  on extraction_runs(user_id, created_at desc);

create index if not exists idx_tasks_user_status
  on tasks(user_id, status);

create index if not exists idx_tasks_source_note_id
  on tasks(source_note_id);

create index if not exists idx_questions_user_status
  on questions(user_id, status);

create index if not exists idx_questions_source_note_id
  on questions(source_note_id);

create index if not exists idx_risks_user_status
  on risks(user_id, status);

create index if not exists idx_risks_source_note_id
  on risks(source_note_id);

create index if not exists idx_decisions_user_created_at
  on decisions(user_id, created_at desc);

create index if not exists idx_facts_user_created_at
  on facts(user_id, created_at desc);

create index if not exists idx_notes_user_created_at
  on notes(user_id, created_at desc);

create index if not exists idx_entities_user_name
  on entities(user_id, name);

create index if not exists idx_memory_item_entities_item
  on memory_item_entities(user_id, item_type, item_id);
