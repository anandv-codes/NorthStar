-- Phase 4 (PR11): categorised recall decks.
-- Run in the Supabase SQL editor AFTER phase4_recall_scheduler.sql. Idempotent.
--
-- recall_decks groups approved recall cards into user-defined categories so a
-- learner can revise a topic on its own. Cards belong to exactly one deck;
-- accepting a candidate copies its deck assignment onto the card (falling back
-- to the user's General deck). Archiving a deck suspends its cards instead of
-- deleting review history.

-- ---------------------------------------------------------------------------
-- recall_decks
-- ---------------------------------------------------------------------------
create table if not exists recall_decks (
  deck_id uuid primary key,
  user_id text not null,
  name text not null,
  description text,
  color text not null default 'neutral',
  is_default boolean not null default false,
  sort_order integer not null default 0,
  archived_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists idx_recall_decks_user_name
  on recall_decks(user_id, lower(name))
  where archived_at is null;

create unique index if not exists idx_recall_decks_user_default
  on recall_decks(user_id)
  where is_default and archived_at is null;

create index if not exists idx_recall_decks_user_order
  on recall_decks(user_id, archived_at, sort_order);

-- ---------------------------------------------------------------------------
-- Deck references: candidates remember the chosen deck before acceptance,
-- cards keep it for filtering and study sessions.
-- ---------------------------------------------------------------------------
alter table recall_candidates
  add column if not exists deck_id uuid references recall_decks(deck_id) on delete set null;

alter table recall_cards
  add column if not exists deck_id uuid references recall_decks(deck_id) on delete set null;

create index if not exists idx_recall_candidates_user_deck
  on recall_candidates(user_id, deck_id);

create index if not exists idx_recall_cards_user_deck_status_due
  on recall_cards(user_id, deck_id, status, next_due);

-- ---------------------------------------------------------------------------
-- Backfill: one General deck per existing user, then attach their cards and
-- candidates. `gen_random_uuid()` is available on Supabase (pgcrypto).
-- ---------------------------------------------------------------------------
insert into recall_decks (deck_id, user_id, name, color, is_default)
select gen_random_uuid(), users.user_id, 'General', 'neutral', true
from (
  select user_id from recall_cards
  union
  select user_id from recall_candidates
) as users
where not exists (
  select 1
  from recall_decks d
  where d.user_id = users.user_id
    and d.is_default
    and d.archived_at is null
);

update recall_cards as c
set deck_id = d.deck_id
from recall_decks as d
where c.deck_id is null
  and d.user_id = c.user_id
  and d.is_default
  and d.archived_at is null;

update recall_candidates as c
set deck_id = d.deck_id
from recall_decks as d
where c.deck_id is null
  and d.user_id = c.user_id
  and d.is_default
  and d.archived_at is null;
