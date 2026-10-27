-- Phase 7: atomic, replayable ingestion.
--
-- Ingestion used to be a dozen separate PostgREST calls: a redelivery between
-- them duplicated every typed memory, and a crash after the LLM call paid for
-- the same extraction twice. This migration makes `note_id` the stable attempt
-- key (one extraction run per note), stores the raw extraction payload on the
-- run *before* the fan-out, and moves the fan-out into one transaction.
--
--   begin_extraction_run(...)   reuse-or-create the run (row lock)
--   save payload                extraction_runs.payload
--   ingest_note_memories(...)   every typed write, or a replay of them
--
-- `fanned_out` is the commit marker: it is set in the same transaction as the
-- writes, so a retry either sees it and replays, or never sees the writes.

alter table extraction_runs
  add column if not exists payload jsonb,
  add column if not exists fanned_out boolean not null default false;

-- Runs created before this migration already fanned out; mark them so a
-- redelivery does not insert the same rows a second time.
update extraction_runs r
   set fanned_out = true
 where r.fanned_out = false
   and (
        exists (select 1 from tasks t where t.extraction_run_id = r.extraction_run_id)
     or exists (select 1 from facts f where f.extraction_run_id = r.extraction_run_id)
     or exists (select 1 from questions q where q.extraction_run_id = r.extraction_run_id)
     or exists (select 1 from decisions d where d.extraction_run_id = r.extraction_run_id)
     or exists (select 1 from concepts c where c.extraction_run_id = r.extraction_run_id)
   );

-- One run per note. If an environment already has two runs for one note this
-- fails loudly rather than silently discarding history; resolve the duplicates
-- first, then re-run.
create unique index if not exists idx_extraction_runs_note_unique
  on extraction_runs(note_id);

drop index if exists idx_extraction_runs_note_id;

-- Reuse-or-create the note's attempt. The upsert takes a row lock, so two
-- concurrent deliveries of the same note serialize here and see one run.
create or replace function begin_extraction_run(
  p_user_id text,
  p_note_id text,
  p_model_name text,
  p_prompt_version text,
  p_now timestamptz
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
  v_run extraction_runs%rowtype;
begin
  insert into extraction_runs (
    extraction_run_id,
    note_id,
    user_id,
    model_name,
    prompt_version,
    status,
    created_at
  ) values (
    gen_random_uuid(),
    p_note_id,
    p_user_id,
    p_model_name,
    p_prompt_version,
    'completed',
    p_now
  )
  on conflict (note_id) do update
     set model_name = excluded.model_name,
         prompt_version = excluded.prompt_version
  returning * into v_run;

  return to_jsonb(v_run);
end;
$$;

-- One transaction for the whole fan-out. Returns the persisted rows so the
-- caller can continue with candidate generation; a replay returns the rows the
-- first attempt wrote instead of inserting them again.
create or replace function ingest_note_memories(
  p_user_id text,
  p_note_id text,
  p_extraction_run_id uuid,
  p_payload jsonb,
  p_now timestamptz
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
  v_fanned_out boolean;
  v_item jsonb;
  v_entity_name text;
  v_entity_row entities%rowtype;
  v_row_id uuid;
  v_comment text;
  v_commitment_id uuid;
  v_inserted integer;
  v_links integer := 0;
  v_contributions integer := 0;
  v_entities jsonb := '[]'::jsonb;
begin
  -- The row lock serialises concurrent deliveries of the same note: the second
  -- one waits here and then sees fanned_out = true.
  select fanned_out
    into v_fanned_out
    from extraction_runs
   where extraction_run_id = p_extraction_run_id
     and note_id = p_note_id
     and user_id = p_user_id
     for update;

  if not found then
    raise exception 'extraction run % not found for note %',
      p_extraction_run_id, p_note_id;
  end if;

  if v_fanned_out then
    return jsonb_build_object(
      'duplicate', true,
      'tasks', coalesce((
        select jsonb_agg(to_jsonb(t) order by t.created_at)
          from tasks t
         where t.extraction_run_id = p_extraction_run_id
      ), '[]'::jsonb),
      'facts', coalesce((
        select jsonb_agg(to_jsonb(f) order by f.created_at)
          from facts f
         where f.extraction_run_id = p_extraction_run_id
      ), '[]'::jsonb),
      'questions', coalesce((
        select jsonb_agg(to_jsonb(q) order by q.created_at)
          from questions q
         where q.extraction_run_id = p_extraction_run_id
      ), '[]'::jsonb),
      'decisions', coalesce((
        select jsonb_agg(to_jsonb(d) order by d.created_at)
          from decisions d
         where d.extraction_run_id = p_extraction_run_id
      ), '[]'::jsonb),
      'concepts', coalesce((
        select jsonb_agg(to_jsonb(c) order by c.created_at)
          from concepts c
         where c.extraction_run_id = p_extraction_run_id
      ), '[]'::jsonb),
      'entities', coalesce((
        select jsonb_agg(distinct to_jsonb(e))
          from entities e
          join memory_item_entities m on m.entity_id = e.entity_id
         where m.user_id = p_user_id
           and m.source_note_id = p_note_id
      ), '[]'::jsonb),
      'links', 0,
      'contributions', 0
    );
  end if;

  -- Entities first: the link inserts below resolve names against this table.
  -- Case-insensitive de-duplication mirrors the Python upsert.
  for v_item in
    select value from jsonb_array_elements(coalesce(p_payload->'entities', '[]'::jsonb))
  loop
    v_entity_name := nullif(btrim(v_item->>'name'), '');
    continue when v_entity_name is null;
    continue when exists (
      select 1
        from jsonb_array_elements(v_entities) e
       where lower(e->>'name') = lower(v_entity_name)
    );

    insert into entities (entity_id, user_id, name, entity_type, created_at)
    values (
      gen_random_uuid(),
      p_user_id,
      v_entity_name,
      nullif(v_item->>'entity_type', ''),
      p_now
    )
    on conflict (user_id, name) do update
       set entity_type = coalesce(excluded.entity_type, entities.entity_type)
    returning * into v_entity_row;

    v_entities := v_entities || jsonb_build_array(to_jsonb(v_entity_row));
  end loop;

  -- tasks
  for v_item in
    select value from jsonb_array_elements(coalesce(p_payload->'tasks', '[]'::jsonb))
  loop
    v_row_id := gen_random_uuid();
    insert into tasks (
      task_id, user_id, source_note_id, extraction_run_id, description,
      status, created_by, confidence, due_date, importance, durability,
      created_at, updated_at, completed_at
    ) values (
      v_row_id,
      p_user_id,
      p_note_id,
      p_extraction_run_id,
      coalesce(v_item->>'description', ''),
      coalesce(nullif(v_item->>'status', ''), 'open'),
      coalesce(nullif(v_item->>'created_by', ''), 'llm'),
      nullif(v_item->>'confidence', '')::numeric,
      nullif(v_item->>'due_date', '')::date,
      nullif(v_item->>'importance', '')::numeric,
      nullif(v_item->>'durability', '')::numeric,
      p_now,
      p_now,
      nullif(v_item->>'completed_at', '')::timestamptz
    );

    for v_entity_name in
      select jsonb_array_elements_text(coalesce(v_item->'entities', '[]'::jsonb))
    loop
      insert into memory_item_entities (
        user_id, entity_id, item_type, item_id, source_note_id, created_at
      )
      select p_user_id, e.entity_id, 'task', v_row_id, p_note_id, p_now
        from entities e
       where e.user_id = p_user_id
         and lower(e.name) = lower(btrim(v_entity_name))
      on conflict do nothing;
      get diagnostics v_inserted = row_count;
      v_links := v_links + v_inserted;
    end loop;
  end loop;

  -- facts
  for v_item in
    select value from jsonb_array_elements(coalesce(p_payload->'facts', '[]'::jsonb))
  loop
    v_row_id := gen_random_uuid();
    insert into facts (
      fact_id, user_id, source_note_id, extraction_run_id, content,
      created_by, confidence, created_at
    ) values (
      v_row_id,
      p_user_id,
      p_note_id,
      p_extraction_run_id,
      coalesce(v_item->>'content', ''),
      coalesce(nullif(v_item->>'created_by', ''), 'llm'),
      nullif(v_item->>'confidence', '')::numeric,
      p_now
    );

    for v_entity_name in
      select jsonb_array_elements_text(coalesce(v_item->'entities', '[]'::jsonb))
    loop
      insert into memory_item_entities (
        user_id, entity_id, item_type, item_id, source_note_id, created_at
      )
      select p_user_id, e.entity_id, 'fact', v_row_id, p_note_id, p_now
        from entities e
       where e.user_id = p_user_id
         and lower(e.name) = lower(btrim(v_entity_name))
      on conflict do nothing;
      get diagnostics v_inserted = row_count;
      v_links := v_links + v_inserted;
    end loop;
  end loop;

  -- questions
  for v_item in
    select value from jsonb_array_elements(coalesce(p_payload->'questions', '[]'::jsonb))
  loop
    v_row_id := gen_random_uuid();
    insert into questions (
      question_id, user_id, source_note_id, extraction_run_id, question,
      status, answer, created_by, confidence, created_at, resolved_at
    ) values (
      v_row_id,
      p_user_id,
      p_note_id,
      p_extraction_run_id,
      coalesce(v_item->>'question', ''),
      coalesce(nullif(v_item->>'status', ''), 'open'),
      nullif(v_item->>'answer', ''),
      coalesce(nullif(v_item->>'created_by', ''), 'llm'),
      nullif(v_item->>'confidence', '')::numeric,
      p_now,
      nullif(v_item->>'resolved_at', '')::timestamptz
    );

    for v_entity_name in
      select jsonb_array_elements_text(coalesce(v_item->'entities', '[]'::jsonb))
    loop
      insert into memory_item_entities (
        user_id, entity_id, item_type, item_id, source_note_id, created_at
      )
      select p_user_id, e.entity_id, 'question', v_row_id, p_note_id, p_now
        from entities e
       where e.user_id = p_user_id
         and lower(e.name) = lower(btrim(v_entity_name))
      on conflict do nothing;
      get diagnostics v_inserted = row_count;
      v_links := v_links + v_inserted;
    end loop;
  end loop;

  -- decisions
  for v_item in
    select value from jsonb_array_elements(coalesce(p_payload->'decisions', '[]'::jsonb))
  loop
    v_row_id := gen_random_uuid();
    insert into decisions (
      decision_id, user_id, source_note_id, extraction_run_id, decision,
      rationale, created_by, confidence, created_at
    ) values (
      v_row_id,
      p_user_id,
      p_note_id,
      p_extraction_run_id,
      coalesce(v_item->>'decision', ''),
      nullif(v_item->>'rationale', ''),
      coalesce(nullif(v_item->>'created_by', ''), 'llm'),
      nullif(v_item->>'confidence', '')::numeric,
      p_now
    );

    for v_entity_name in
      select jsonb_array_elements_text(coalesce(v_item->'entities', '[]'::jsonb))
    loop
      insert into memory_item_entities (
        user_id, entity_id, item_type, item_id, source_note_id, created_at
      )
      select p_user_id, e.entity_id, 'decision', v_row_id, p_note_id, p_now
        from entities e
       where e.user_id = p_user_id
         and lower(e.name) = lower(btrim(v_entity_name))
      on conflict do nothing;
      get diagnostics v_inserted = row_count;
      v_links := v_links + v_inserted;
    end loop;
  end loop;

  -- concepts
  for v_item in
    select value from jsonb_array_elements(coalesce(p_payload->'concepts', '[]'::jsonb))
  loop
    v_row_id := gen_random_uuid();
    insert into concepts (
      concept_id, user_id, source_note_id, extraction_run_id, concept,
      status, created_by, confidence, created_at
    ) values (
      v_row_id,
      p_user_id,
      p_note_id,
      p_extraction_run_id,
      coalesce(v_item->>'concept', ''),
      coalesce(nullif(v_item->>'status', ''), 'open'),
      coalesce(nullif(v_item->>'created_by', ''), 'llm'),
      nullif(v_item->>'confidence', '')::numeric,
      p_now
    );

    for v_entity_name in
      select jsonb_array_elements_text(coalesce(v_item->'entities', '[]'::jsonb))
    loop
      insert into memory_item_entities (
        user_id, entity_id, item_type, item_id, source_note_id, created_at
      )
      select p_user_id, e.entity_id, 'concept', v_row_id, p_note_id, p_now
        from entities e
       where e.user_id = p_user_id
         and lower(e.name) = lower(btrim(v_entity_name))
      on conflict do nothing;
      get diagnostics v_inserted = row_count;
      v_links := v_links + v_inserted;
    end loop;
  end loop;

  -- Long-term-goal contributions. Only active goals owned by this user are
  -- accepted, and `(commitment_id, note_id)` de-duplication preserves a user's
  -- edit when the same note is processed again.
  for v_item in
    select value from jsonb_array_elements(
      coalesce(p_payload->'commitment_contributions', '[]'::jsonb)
    )
  loop
    v_commitment_id := nullif(btrim(v_item->>'commitment_id'), '')::uuid;
    v_comment := btrim(regexp_replace(coalesce(v_item->>'comment', ''), '\s+', ' ', 'g'));
    continue when v_commitment_id is null or v_comment = '';

    if length(v_comment) > 240 then
      v_comment := rtrim(left(v_comment, 239)) || '.';
    end if;

    if not exists (
      select 1
        from user_commitments
       where commitment_id = v_commitment_id
         and user_id = p_user_id
         and status = 'active'
    ) then
      continue;
    end if;

    insert into commitment_contributions (
      contribution_id, commitment_id, user_id, note_id, comment,
      created_at, updated_at
    ) values (
      gen_random_uuid(), v_commitment_id, p_user_id, p_note_id, v_comment,
      p_now, p_now
    )
    on conflict (commitment_id, note_id) do nothing;
    get diagnostics v_inserted = row_count;
    v_contributions := v_contributions + v_inserted;
  end loop;

  update extraction_runs
     set fanned_out = true
   where extraction_run_id = p_extraction_run_id;

  return jsonb_build_object(
    'duplicate', false,
    'tasks', coalesce((
      select jsonb_agg(to_jsonb(t) order by t.created_at)
        from tasks t
       where t.extraction_run_id = p_extraction_run_id
    ), '[]'::jsonb),
    'facts', coalesce((
      select jsonb_agg(to_jsonb(f) order by f.created_at)
        from facts f
       where f.extraction_run_id = p_extraction_run_id
    ), '[]'::jsonb),
    'questions', coalesce((
      select jsonb_agg(to_jsonb(q) order by q.created_at)
        from questions q
       where q.extraction_run_id = p_extraction_run_id
    ), '[]'::jsonb),
    'decisions', coalesce((
      select jsonb_agg(to_jsonb(d) order by d.created_at)
        from decisions d
       where d.extraction_run_id = p_extraction_run_id
    ), '[]'::jsonb),
    'concepts', coalesce((
      select jsonb_agg(to_jsonb(c) order by c.created_at)
        from concepts c
       where c.extraction_run_id = p_extraction_run_id
    ), '[]'::jsonb),
    'entities', v_entities,
    'links', v_links,
    'contributions', v_contributions
  );
end;
$$;
