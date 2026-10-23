-- Phase 4 (accept RPC): idempotent candidate -> card transition in one statement.
-- Run in the Supabase SQL editor AFTER phase4_recall_decks.sql. Idempotent.
--
-- Why an RPC: the previous flow inserted the card, then updated the candidate in
-- two PostgREST calls. A retry could hit the (user_id, candidate_id) unique
-- index, and a crash between the two writes left an orphan card. Locking the
-- candidate row makes concurrent accepts serialize, and checking for an
-- existing card first makes a retry (or an orphan from the old flow) return the
-- card instead of erroring.
--
-- Returns one of:
--   {"status": "carded", "card": {...}}   success or idempotent retry
--   {"status": "not_found"}               no candidate for this user
--   {"status": "already_carded"}          status says carded but the card is gone

create or replace function accept_recall_candidate(
  p_user_id text,
  p_candidate_id uuid,
  p_card jsonb,
  p_now timestamptz
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
  v_candidate recall_candidates%rowtype;
  v_card recall_cards%rowtype;
begin
  select *
    into v_candidate
    from recall_candidates
   where user_id = p_user_id
     and candidate_id = p_candidate_id
     for update;

  if not found then
    return jsonb_build_object('status', 'not_found');
  end if;

  -- Retry, or an orphan card created before this RPC existed.
  select *
    into v_card
    from recall_cards
   where user_id = p_user_id
     and candidate_id = p_candidate_id
   limit 1;

  if found then
    update recall_candidates
       set status = 'carded',
           deck_id = v_card.deck_id,
           decided_at = coalesce(decided_at, p_now),
           updated_at = p_now
     where user_id = p_user_id
       and candidate_id = p_candidate_id;
    return jsonb_build_object('status', 'carded', 'card', to_jsonb(v_card));
  end if;

  if v_candidate.status = 'carded' then
    return jsonb_build_object('status', 'already_carded');
  end if;

  insert into recall_cards (
    card_id,
    user_id,
    candidate_id,
    deck_id,
    question,
    answer,
    source_note_ids,
    status,
    state,
    learning_step,
    interval,
    easiness,
    repetitions,
    lapses,
    review_count,
    next_due
  ) values (
    gen_random_uuid(),
    p_user_id,
    p_candidate_id,
    nullif(p_card->>'deck_id', '')::uuid,
    p_card->>'question',
    p_card->>'answer',
    array(
      select jsonb_array_elements_text(
        coalesce(p_card->'source_note_ids', '[]'::jsonb)
      )
    ),
    coalesce(p_card->>'status', 'active'),
    coalesce(p_card->>'state', 'new'),
    coalesce((p_card->>'learning_step')::integer, 0),
    coalesce((p_card->>'interval')::integer, 0),
    coalesce((p_card->>'easiness')::numeric, 2.5),
    coalesce((p_card->>'repetitions')::integer, 0),
    coalesce((p_card->>'lapses')::integer, 0),
    coalesce((p_card->>'review_count')::integer, 0),
    coalesce((p_card->>'next_due')::timestamptz, p_now)
  )
  returning * into v_card;

  update recall_candidates
     set status = 'carded',
         deck_id = v_card.deck_id,
         decided_at = p_now,
         updated_at = p_now
   where user_id = p_user_id
     and candidate_id = p_candidate_id;

  return jsonb_build_object('status', 'carded', 'card', to_jsonb(v_card));
end;
$$;
