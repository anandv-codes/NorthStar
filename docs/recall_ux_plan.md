# NorthStar Recall-First UX Plan

Companion to `docs/recall_pivot_implementation_plan.md` (product source: `final.md`).
Scope: re-center the web app on **Capture → Understand → Remember → Act** while
keeping the existing plain, inline-styled React aesthetic (no CSS framework, no
design-system rewrite).

Status: **implemented (PR9–PR10).** Backend PR1–PR8 and the recall-first UI slices
(routing/nav, Today, Review due + suggestions, Notes + per-note recall toggle, Ask)
are in the repo. Verified with `tsc --noEmit` and `vite build`. See
"Tooling blocker" at the end for the `uipro` note; the UI was hand-written per the
approved path.

---

## 1. Goals

1. Landing surface answers one question: **"What should I remember or do today?"**
2. Review (Recall) is a first-class, low-friction loop: one question at a time,
   reveal, grade, next.
3. Capture stays one tap away from every screen.
4. Chat becomes a secondary tool ("Ask"), not the default landing page.
5. No new dependencies, no CSS files, no component-library migration — extend the
   existing inline-style components.

Non-goals (this pass): calendar UI, analytics dashboards, multi-user sharing,
mobile native app, dark mode.

---

## 2. Current state (inventory)

- `frontend/src/app/App.tsx` — single monolith (813 lines). Hash routes:
  `#/login`, `#/register`, `#/dashboard`, `#/add-note`, `#/chat`. Unknown/empty
  hash falls through to `chat`.
- `getRouteFromHash()` defaults to `chat`; login/register redirect to `#/chat`.
- Dashboard is a vertical stack of plain sections under
  `frontend/src/features/dashboard/components/`:
  `TasksSection`, `QuestionsSection`, `RisksSection`, `ConceptsSection`,
  `RecentMemorySection`, `DailyWeeklySummarySection`.
- API layer: `frontend/src/shared/api/httpClient.ts` (single `fetch` wrapper with
  bearer token + refresh-on-401). Auth: `frontend/src/shared/auth/`.
- Aesthetic tokens in use (reuse these exact values):
  - page background `#f7f5f2`, cards `#fff`, borders `#e5e0d8` / `#cfc7bc`,
    muted text `#666` / `#777`, accent `#111`, error `#b00020`.
  - radii 12–16px, gaps 8–16px, section headings bold, `maxWidth` 900 (app) or
    420 (auth).

Available backend endpoints today (recall):

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/recall/candidates?status=suggested&limit=` | suggested questions, answer hidden |
| `POST` | `/recall/candidates/{id}/accept` | generates answer, creates card, returns `card` |
| `POST` | `/recall/candidates/{id}/reject` | body `{feedback?}` |
| `GET` | `/recall/due?limit=` | due cards (includes answer) |
| `POST` | `/recall/cards/{id}/review` | `{grade: 1|3|4|5, elapsed_ms?}` |
| `PATCH` | `/notes/{id}/recall` | `{enabled: bool}` → `{recall_status, questions_generated, suggestions_total}` |

Gaps to fill for the UX (small, additive):

- No `GET /notes` list (use existing `GET /memory/recent` for now, or add a thin
  list endpoint later).
- No `/dashboard/today` aggregate. Today can be composed client-side from
  `fetchTasks`, `fetchRecentMemory`, `GET /recall/due`,
  `GET /recall/candidates`, and the existing summary endpoints, avoiding a new
  backend surface for the first iteration.
- `TaskResponse` currently has no `due_date`; commitments need it. Defer the
  committed-actions card until `due_date` is exposed (Phase 6/Act), or show tasks
  without due grouping for now.

---

## 3. Information architecture

Primary (recall loop):

1. **Today** — default route after login.
2. **Review** — due cards, then suggested questions.

Secondary:

3. **Capture** — add a note (existing `AddNotePage`).
4. **Notes** — memory browser (summary, units, provenance, recall toggle).
5. **Ask** — existing chat, relabeled.

Utility: **Settings** (logout; per-note defaults later).

### 3.1 Nav model

Keep hash routing and the existing plain header. Replace the ad-hoc
`Chat | Add Note | Dashboard` links with a shared `AppNav` component rendered at
the top of every authenticated page.

Desktop (single row, left-aligned brand, right-aligned primary CTA):

```
NorthStar        Today   Review   Notes   Ask        [+ Capture]
```

Mobile (`max-width: 640px`, detected via a small `useIsMobile` hook using
`window.matchMedia`): brand row + horizontally scrollable link row; `Capture`
becomes a full-width button under the header.

Route map (extend `Route` union):

| Route | Hash | Purpose |
| --- | --- | --- |
| `login` | `#/login` | |
| `register` | `#/register` | |
| `today` | `#/today` | **new default** |
| `review` | `#/review` | new |
| `notes` | `#/notes` | new |
| `note` | `#/notes/:id` | note detail |
| `ask` | `#/ask` | renamed from `chat` |
| `capture` | `#/capture` | renamed from `add-note` |

Behavior changes:

- `getRouteFromHash()` unknown/empty → `today`.
- After login/register → `#/today`.
- After note completes → `#/today` (so the user sees new items land).
- Keep `#/chat` and `#/add-note` as aliases mapping to `ask` / `capture` to avoid
  breaking bookmarks.

---

## 4. Today page (`#/today`)

Vertical stack, `maxWidth: 900`, same card styling as dashboard sections.

Sections, in order:

1. **Header summary line** — "N due · M new to consider · K commitments".
2. **Review CTA card**
   - If due > 0: big primary button `Review N due cards` → `#/review`.
   - If due == 0 and suggestions > 0: `Consider M suggested questions` → `#/review?tab=suggested`.
   - If both 0: calm empty state — "You're caught up. Nothing due right now."
3. **Suggested questions** (max 3 inline) — question text only; `Accept` /
   `Skip` buttons. On `Accept`, reveal answer inline and show "Added to review".
   Reuse `RecallSuggestionResponse` fields (`question`, `item_type`,
   `source_note_id`, `durability`).
4. **Commitments / tasks due** — reuse `TasksSection` but filtered to open tasks;
   group by "Overdue / Today / This week" once `due_date` is exposed.
5. **Highlights** — reuse `RecentMemorySection` (recent memory) and/or
   `QuestionsSection`/`RisksSection` reduced to a few rows with a "See all".
6. **Summary status** — reuse `DailyWeeklySummarySection` (keep as-is).
7. **Quick capture** — 3-row textarea + `Save note` posting to
   `POST /notes`, then navigate to `#/today` and optimistically show a
   "Processing…" chip. (Also available as `#/capture` full page.)

Data loading: one `loadToday()` `Promise.all` of
`fetchTasks`, `fetchRecentMemory`, `fetchDailySummary`, `fetchWeeklySummary`,
`fetchDueCards`, `fetchSuggestions`. Renders per-section loading/empty/error
independently so one failure does not blank the page.

---

## 5. Review page (`#/review`)

Two tabs within one page.

### 5.1 Tab: Due cards

Session shell (reuse the card aesthetic):

```
┌───────────────────────────────┐
│  12 due            [End session] │
│  ●●●●●●○○○○ progress             │
│                                 │
│  Question (large, centered)     │
│                                 │
│  [ Show answer ]                │
└───────────────────────────────┘
```

- `Show answer` reveals the answer and the four grade buttons.
- Grades map exactly to the API: `Again=1`, `Hard=3`, `Good=4`, `Easy=5`
  (never send `2`).
- Keyboard: `Space`/`Enter` = show answer; `1`=Again, `2`=Hard, `3`=Good, `4`=Easy
  (display the digit hints; the underlying value sent is 1/3/4/5).
- Send `elapsed_ms` measured from question render to grade click.
- On submit: remove the card from the local queue, show the next card; do not
  block on a refetch. Show a running "reviewed" counter.
- End state: "Session complete — N reviewed. Great work." with links back to
  `#/today` and `#/notes`.
- Errors: if `review` returns 404 (card already gone) skip it; surface other
  errors as an inline `#b00020` message with a Retry button.

### 5.2 Tab: Suggested (`?tab=suggested`)

- One suggestion at a time: question only, with a muted `item_type` chip and a
  "from note" link to `#/notes/:source_note_id`.
- Actions: `Accept` (calls accept; shows "Generating answer…" spinner, then the
  answer and an "Added to review" confirmation) and `Skip` (calls reject;
  advances immediately).
- Accept is network+LLM bound: disable both buttons while in flight, and on
  failure keep the suggestion and show a Retry.
- Empty state: "No suggested questions. Capture a note with recall enabled, or
  turn recall on for an existing note."

---

## 6. Notes page (`#/notes`) and detail (`#/notes/:id`)

### 6.1 List

- Source: `GET /memory/recent?limit=` initially; render note cards with
  `raw_text` excerpt, `created_at`, and a recall badge.
- Recall badge derived from note fields: `off` (muted), `pending` (amber),
  `ready` (green), `failed` (`#b00020`).

### 6.2 Detail

- Reuse `getNoteMemory(note_id)` for summary, typed items, entities, provenance.
- **Recall toggle** (the per-note opt-in) lives here as a labelled switch:
  - Off → On: `PATCH /notes/{id}/recall {enabled:true}`; show "Generating
    questions…" (synchronous backend call) then "N questions ready".
  - On → Off: `{enabled:false}`; show "Recall off".
  - Show `recall_status` and, when `questions_generated > 0`,
    `suggestions_total`.
- Note processing states (`processing`, `failed`) reuse the existing
  `AddNotePage` polling pattern; add a `failed` state with a "Reprocess" affordance
  (endpoint is planned, not implemented — hide until then).

---

## 7. Ask page (`#/ask`)

Existing `ChatPage` renamed; only changes:

- Title "Ask NorthStar", subtitle explains it searches memory.
- Header links replaced by `AppNav`.
- Remove the `Dashboard` button (nav handles it).
- `sending` label stays "Thinking…".

---

## 8. Shared states and copy

- **Loading:** inline `Loading…` text in `#666` (match existing).
- **Empty:** one sentence + one action link; never an empty box.
- **Error:** `#b00020` text + `Retry` button; per section.
- **Optimistic:** capture shows a `Processing…` chip; accept/skip update the
  local queue immediately.
- Copy uses "suggested question", "review", "grade", "skip" — never "SM-2",
  "candidate", "card state".
- Accessibility: buttons are real `<button>`; toggles use `aria-pressed`; the
  review session traps focus on the grade buttons; grade digits are visible
  hints, and `Space` reveals.

---

## 9. Mobile layout

- Breakpoint `640px` via `window.matchMedia("(max-width: 640px)")` in a
  `useIsMobile()` hook (no CSS files).
- Nav collapses as described in 3.1.
- Review card font scales up; grade buttons become a 2×2 grid, full width.
- Today sections remain a single column; `maxWidth` becomes `100%` with 16px
  padding.

---

## 10. File plan (new, under existing conventions)

```
frontend/src/
  app/
    App.tsx                 (add routes, use AppNav, re-center defaults)
  shared/
    ui/
      AppNav.tsx            (header nav + Capture CTA)
      useIsMobile.ts
      Card.tsx              (thin wrapper: white card, border, radius, padding)
      states.tsx            (Loading, Empty, ErrorLine)
  features/
    today/
      TodayPage.tsx
      QuickCapture.tsx
      ReviewCta.tsx
    review/
      ReviewPage.tsx
      ReviewSession.tsx     (due cards, reveal + grade)
      SuggestedQuestions.tsx
    notes/
      NotesPage.tsx
      NoteDetailPage.tsx
      RecallToggle.tsx
    ask/
      AskPage.tsx           (move ChatPage here)
```

`httpClient.ts` additions (typed, mirrored from backend schemas):

```ts
fetchDueCards(limit?)           // GET /recall/due
fetchSuggestions(limit?)        // GET /recall/candidates?status=suggested
acceptSuggestion(id)            // POST /recall/candidates/{id}/accept
rejectSuggestion(id, feedback?) // POST /recall/candidates/{id}/reject
reviewCard(id, grade, elapsedMs?) // POST /recall/cards/{id}/review
setNoteRecall(noteId, enabled)  // PATCH /notes/{id}/recall
```

Types mirror `RecallSuggestionResponse`, `RecallCardResponse`,
`RecallDecisionResponse`, `RecallReviewResult`, `NoteRecallToggleResponse`.

---

## 11. Phasing

1. **PR9a — nav + routing (done):** `AppNav`, `Route` union, default `today`,
   login redirect to `#/today`, aliases for `#/chat` / `#/add-note`.
2. **PR9b — Review (due cards) (done):** `ReviewPage` + `ReviewSession` + client
   functions + keyboard/grade mapping.
3. **PR9c — Suggested questions (done):** `SuggestedQuestions` + accept/skip flow.
4. **PR10a — Today (done):** compose sections from existing endpoints; QuickCapture.
5. **PR10b — Notes + recall toggle (done):** list, detail, `RecallToggle`.
6. **PR10c — Summaries re-centered** on recall workload (copy + order only) — not
   yet; summaries still render as before inside Today.

Each slice is independently shippable and testable with the existing backend.

---

## 12. Acceptance checks

- Login lands on `#/today`; unknown hashes land on `#/today`.
- Review session sends only `1|3|4|5`; a full session updates `next_due` and the
  card disappears from `/recall/due`.
- Accept shows the question first and only reveals the answer after the API call
  returns a card; Skip removes the suggestion.
- Per-note toggle off→on produces suggestions synchronously and shows a count.
- Every section has loading, empty, and error states; one failed call does not
  blank the page.
- Aesthetic unchanged: same colors, radii, spacing, inline styles; no new
  runtime dependencies.

---

## 13. Tooling blocker

`uipro init --ai opencode` could not be run: `uipro` is not installed,
is not published on npm (E404), and has no PyPI distribution. This plan does not
depend on it. UI implementation should proceed with hand-written React +
inline styles as described above unless the correct `uipro` source/installation
is provided.
