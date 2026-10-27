-- Phase 6: one note-status vocabulary.
--
-- Before this, `completed` was written when the LLM returned, *before*
-- `index_note` ran, and indexing failures were swallowed. A note could
-- therefore be "completed" and invisible to retrieval.
--
--   processing --> enriched --> indexed
--             \--> failed  <--/
--
-- `indexed` is the only success terminal state.

alter table notes
  add column if not exists indexed_at timestamptz,
  add column if not exists index_error text;

-- Legacy rows cannot be distinguished from successfully indexed ones: the old
-- pipeline set `completed` before indexing and discarded the error. They are
-- mapped to `indexed` with a backfilled timestamp. Any note whose indexing
-- silently failed can be repaired by reprocessing it.
update notes
   set status = 'indexed',
       indexed_at = coalesce(indexed_at, processed_at)
 where status = 'completed';

-- Anything outside the vocabulary is a stuck note; let a retry finish it.
update notes
   set status = 'processing'
 where status not in ('processing', 'enriched', 'indexed', 'failed');

-- Postgres has no `add constraint if not exists`, so guard it explicitly.
do $$
begin
  if not exists (
    select 1
      from pg_constraint
     where conname = 'notes_status_check'
       and conrelid = 'notes'::regclass
  ) then
    alter table notes
      add constraint notes_status_check
      check (status in ('processing', 'enriched', 'indexed', 'failed'));
  end if;
end $$;
