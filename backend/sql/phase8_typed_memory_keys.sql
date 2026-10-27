-- Phase 8: natural keys for typed memories.
--
-- Phase 7 made the fan-out one transaction with a stable attempt key, so a
-- redelivery cannot duplicate rows. These constraints turn that from a
-- property of the worker into an invariant of the storage layer.
--
-- The item-5 sketch also asked for a partial unique index on the active
-- extraction run per note. Phase 7 already added the stronger version: a full
-- unique index on extraction_runs(note_id).
--
-- `content_hash` is the md5 of the normalized item text (trim + lower), so
-- "same content, different whitespace/case" is the same memory. Manual rows
-- created by chat tools have no extraction run and keep a NULL hash; Postgres
-- treats NULLs as distinct, so those rows are deliberately outside the key.

alter table tasks
  add column if not exists content_hash text;
alter table facts
  add column if not exists content_hash text;
alter table questions
  add column if not exists content_hash text;
alter table decisions
  add column if not exists content_hash text;
alter table concepts
  add column if not exists content_hash text;

update tasks
   set content_hash = md5(lower(btrim(description)))
 where content_hash is null;
update facts
   set content_hash = md5(lower(btrim(content)))
 where content_hash is null;
update questions
   set content_hash = md5(lower(btrim(question)))
 where content_hash is null;
update decisions
   set content_hash = md5(lower(btrim(decision)))
 where content_hash is null;
update concepts
   set content_hash = md5(lower(btrim(concept)))
 where content_hash is null;

-- If an environment already has two identical items in one run, these fail
-- loudly instead of silently deleting a user-visible row. Resolve the
-- duplicates first, then re-run.
create unique index if not exists idx_tasks_note_run_content
  on tasks(source_note_id, extraction_run_id, content_hash);
create unique index if not exists idx_facts_note_run_content
  on facts(source_note_id, extraction_run_id, content_hash);
create unique index if not exists idx_questions_note_run_content
  on questions(source_note_id, extraction_run_id, content_hash);
create unique index if not exists idx_decisions_note_run_content
  on decisions(source_note_id, extraction_run_id, content_hash);
create unique index if not exists idx_concepts_note_run_content
  on concepts(source_note_id, extraction_run_id, content_hash);

-- Same fan-out as phase 7, plus the content key. A duplicate inside one
-- payload now resolves to the existing row (the no-op UPDATE returns its id)
-- instead of aborting the whole note.
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
      created_at, updated_at, completed_at, content_hash
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
      nullif(v_item->>'completed_at', '')::timestamptz,
      md5(lower(btrim(coalesce(v_item->>'description', ''))))
    )
    on conflict (source_note_id, extraction_run_id, content_hash) do update
       set description = tasks.description
    returning task_id into v_row_id;

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
      created_by, confidence, created_at, content_hash
    ) values (
      v_row_id,
      p_user_id,
      p_note_id,
      p_extraction_run_id,
      coalesce(v_item->>'content', ''),
      coalesce(nullif(v_item->>'created_by', ''), 'llm'),
      nullif(v_item->>'confidence', '')::numeric,
      p_now,
      md5(lower(btrim(coalesce(v_item->>'content', ''))))
    )
    on conflict (source_note_id, extraction_run_id, content_hash) do update
       set content = facts.content
    returning fact_id into v_row_id;

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
      status, answer, created_by, confidence, created_at, resolved_at,
      content_hash
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
      nullif(v_item->>'resolved_at', '')::timestamptz,
      md5(lower(btrim(coalesce(v_item->>'question', ''))))
    )
    on conflict (source_note_id, extraction_run_id, content_hash) do update
       set question = questions.question
    returning question_id into v_row_id;

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
      rationale, created_by, confidence, created_at, content_hash
    ) values (
      v_row_id,
      p_user_id,
      p_note_id,
      p_extraction_run_id,
      coalesce(v_item->>'decision', ''),
      nullif(v_item->>'rationale', ''),
      coalesce(nullif(v_item->>'created_by', ''), 'llm'),
      nullif(v_item->>'confidence', '')::numeric,
      p_now,
      md5(lower(btrim(coalesce(v_item->>'decision', ''))))
    )
    on conflict (source_note_id, extraction_run_id, content_hash) do update
       set decision = decisions.decision
    returning decision_id into v_row_id;

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
      status, created_by, confidence, created_at, content_hash
    ) values (
      v_row_id,
      p_user_id,
      p_note_id,
      p_extraction_run_id,
      coalesce(v_item->>'concept', ''),
      coalesce(nullif(v_item->>'status', ''), 'open'),
      coalesce(nullif(v_item->>'created_by', ''), 'llm'),
      nullif(v_item->>'confidence', '')::numeric,
      p_now,
      md5(lower(btrim(coalesce(v_item->>'concept', ''))))
    )
    on conflict (source_note_id, extraction_run_id, content_hash) do update
       set concept = concepts.concept
    returning concept_id into v_row_id;

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
