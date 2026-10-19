-- Phase 4 (PR8): Anki-style scheduler state on recall_cards.
-- Run in the Supabase SQL editor AFTER phase4_recall.sql. Idempotent.
--
-- state:         new | learning | review | relearning
-- learning_step: index into the configured learning/relearning steps

alter table recall_cards
  add column if not exists state text not null default 'new',
  add column if not exists learning_step integer not null default 0;

create index if not exists idx_recall_cards_user_state_due
  on recall_cards(user_id, state, next_due);
