# Entity Deprecation: Risks

**Status:** Risks deprecated as of 2026-10-26  
**Decision:** Stop extracting, storing, exposing, and rendering the `risks` entity. Existing risk rows stay in the database until a separate contract step is explicitly approved.  
**Replacement:** Tasks cover actionable follow-ups; questions cover unresolved open loops; decisions cover resolved choices. There is no one-to-one risk replacement.

## Why

The risks entity duplicated information already captured by tasks, questions, and decisions while adding its own schema, API, prompts, dashboard section, and chat tools. Removing it reduces extraction noise, UI surface area, and maintenance cost.

Risk **flags** are not part of this deprecation. `rewrite_risk_flags` and `detect_rewrite_risks` describe query-rewrite safety and must remain.

## Scope

Removed in this change:

- Risk extraction schema, prompt fields, metadata projection, and worker persistence.
- Risk repository/service methods, `/risks` routes, note-memory fields, recent-memory fields, and summary statistics.
- Risk chat tools, tool context, dashboard panel, note-detail section, client types, and API calls.
- Risk marketing copy and active architecture documentation.
- Risk-specific tests and fixtures.

Intentionally retained:

- The `risks` table and its existing rows.
- The `SUPABASE_RISKS_TABLE` database table itself, but not the environment-variable reader.
- Historical planning documents under `docs/` that describe earlier proposals.
- Query-rewrite risk flags and guarded-rewrite wording.

## Safe Migration Sequence

This follows expand/contract. The code removal and the table drop are separate deploys.

### Phase 1: Remove consumers

1. Remove risk extraction, persistence, API, chat, UI, and tests in one code change.
2. Deploy the code with the `risks` table still present.
3. Verify no application code reads or writes `risks`.

### Phase 2: Observe

Run in production for a full release window. Watch for:

- 404s from clients still calling `/risks`.
- Extraction outputs that still contain `risks` (they are ignored by the typed schema and metadata projection).
- Dashboard or note-detail requests returning unexpected fields.

Because the frontend and backend ship together here, a 404 would indicate an old cached frontend or an external consumer.

### Phase 3: Contract

Do this only after explicit approval and a verified backup.

1. Take a full database backup. This is the down path.
2. Archive or export `risks` rows and `memory_item_entities` rows with `item_type = 'risk'`.
3. Delete risk entity links.
4. Drop `risks` in a separate deploy.
5. Remove the table from `backend/sql/phase3_work_memory.sql` and the README table list.

Contract is intentionally not automated in this repository yet. A destructive migration without a tested restore path would violate the deprecation policy.

## Repeatable Entity-Deprecation Checklist

Use this checklist for the next entity, not just risks.

### 1. Decide

- Confirm the entity no longer provides unique value.
- Identify the replacement or state explicitly that none exists.
- Quantify consumers: backend routes, chat tools, frontend screens, prompts, docs, tests, external clients.
- Decide data disposition: retain dormant, archive, or drop.
- Default to retain. Destructive schema changes require separate approval.

### 2. Inventory

Search for the singular, plural, ID field, response type, and UI component names:

```bash
grep -RIn --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=.git \
  -E "risk|Risk|risk_id|RiskResponse|RiskWatch" backend frontend docs README.md
```

Classify every match:

- Entity usage: remove.
- Unrelated English usage or safety flag: keep.
- Historical plan: keep, but label it historical if it is likely to be mistaken for current behavior.

### 3. Remove in thin slices

Recommended order:

1. Extraction schema and prompt.
2. Worker persistence and metadata projection.
3. Repository, service, and API route.
4. Note snapshots, recent memory, and summaries.
5. Chat tools and tool context.
6. Frontend API client and UI.
7. Tests and fixtures.
8. Active docs and marketing copy.

Run tests after each slice that can compile independently.

### 4. Keep the database dormant

- Leave the table in place during the code deploy.
- Do not dual-write during removal; there is no new writer.
- Do not drop the table in the same deploy as the code change.
- Take a backup before any destructive step.
- Test restore on staging before production.

### 5. Verify

Inspect the diff for accidental removal of unrelated safety behavior. Then run:

```bash
grep -RIn --exclude-dir=__pycache__ --exclude-dir=node_modules --exclude-dir=dist \
  -E "RiskResponse|RiskUpdateRequest|ExtractedRisk|MemoryRisk|RiskWatch|fetchRisks|patchRiskStatus|insert_risks|query_risks|update_risk_item" \
  backend frontend
```

Expected result: no matches in application code.

Run the relevant backend tests, then the frontend checks:

```bash
# backend examples
python -m pytest backend/tests/test_extraction_v2.py \
  backend/tests/test_candidate_engine.py \
  backend/tests/test_summary_focus.py

# frontend
cd frontend
node node_modules/typescript/bin/tsc --noEmit
node node_modules/vite/bin/vite.js build
```

If local Python dependencies are missing, report which tests could not run rather than claiming a full pass.

### 6. Finish

- Remove deprecation notices once the entity is fully gone.
- Update the contract checklist with the actual data decision.
- Delete the deprecation document only after the contract phase is complete and the history is captured in git.
