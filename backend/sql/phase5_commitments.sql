-- Phase 5: user-authored long-term commitments.
--
-- These replace the old note-extracted `commitments` table for the product
-- surface. The legacy table is intentionally left untouched so existing data
-- is not destroyed; new writes go to `user_commitments` only.
--
-- Run in the Supabase SQL editor AFTER phase3_work_memory.sql. Every statement
-- is idempotent, so re-running this file is safe.

create table if not exists user_commitments (
  commitment_id uuid primary key,
  user_id text not null,
  text text not null,
  progress integer not null default 0 check (progress between 0 and 100),
  status text not null default 'active' check (status in ('active', 'completed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);

create index if not exists idx_user_commitments_user_status
  on user_commitments(user_id, status, created_at desc);

-- One contribution per goal per note. The worker may retry a note; this
-- uniqueness is what makes auto-write idempotent and protects user edits.
create table if not exists commitment_contributions (
  contribution_id uuid primary key,
  commitment_id uuid not null references user_commitments(commitment_id) on delete cascade,
  user_id text not null,
  note_id text not null references notes(note_id) on delete cascade,
  comment text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  edited_at timestamptz
);

create unique index if not exists idx_commitment_contributions_commitment_note
  on commitment_contributions(commitment_id, note_id);

create index if not exists idx_commitment_contributions_user_created
  on commitment_contributions(user_id, created_at desc);

create index if not exists idx_commitment_contributions_note
  on commitment_contributions(note_id);
