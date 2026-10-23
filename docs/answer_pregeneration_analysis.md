# Pre-generating answers with questions: how much does it help?

**Question:** today only the question is generated during note processing; the answer is
generated on reveal or accept. What changes if every question ships with its answer?

**Short answer:** there are two ways to read "along with":

- **Two calls** (question, then answer): removes LLM latency from accept, but costs an answer
  call for every candidate instead of only the ones users look at — roughly **1.2–1.6× the
  current LLM cost** at typical accept rates, breaking even only if almost every suggestion
  is revealed or accepted.
- **One combined call** (a single prompt returns `{question, answer}`): also removes accept
  latency, but is much closer to **cost-neutral** and can even be slightly cheaper, because
  the answer no longer re-sends the source note that the question call already paid for. The
  cost moves from "per accepted card" to "per candidate", and the risk moves from cost to
  quality coupling.

Either way it is a latency/reliability trade, not a pure optimisation. Measure the reveal and
accept rates before choosing.

## Decision (implemented 2026-10-24)

The project chose **one combined prompt** and runs it in the existing asynchronous note
worker (the SQS job). Implementation notes:

- The single prompt returns `{"question": "...", "answer": "..."}`; both fields are validated
  independently and persisted in the same conditional candidate update. A candidate becomes
  `suggested` only once the pair is written, so a visible suggestion always has its answer.
- If the question is valid but the answer is not grounded after retries, the question is kept
  with `answer = None` and the reason is recorded in `rationale.answer_reason`; reveal/accept
  regenerates the answer synchronously.
- Editing a suggestion's question clears the stored answer, so the next reveal/accept cannot
  serve an answer written for the old question.
- The worker's write is conditional on the candidate still being `eligible`. Duplicate SQS
  delivery (or a user request that won the candidate) therefore cannot overwrite it.
- **Priority:** the "5 suggestions, reveal card 5 while answers are processing" problem does
  not arise for visible cards under pair visibility. If an answer is missing because of a
  partial failure, reveal generates it synchronously, so the user's request always outranks
  background work. A narrow overlap can still cost one duplicate LLM call; a claim/lease
  column is the next step only if that cost is measurable.


---

## 1. Flow before this change

The table below describes the pre-combined-prompt flow that motivated the analysis.

| Stage | Where | LLM calls |
| --- | --- | --- |
| Note ingestion | `note_processor.py:291` → `generate_questions` | 1 per eligible candidate (up to 2 attempts) |
| Question written | `question_service.py:87-93` | — |
| User reveals answer | `POST /recall/candidates/{id}/answer` → `generate_answer_for_candidate` | 1 (cached afterwards) |
| User accepts | `review_service.py:59-74`; generates only if `answer` is empty | 0 if revealed, else 1 |
| Batch accept | `accept_candidates` loops per candidate | 0–1 per candidate, **sequential** |
| User ignores/rejects | — | 0 answer calls (unless revealed) |

Key detail: the reveal endpoint persists the answer on the candidate
(`question_service.py:157`), so reveal-then-accept is already instant. The expensive path is
**accept without revealing** — especially "Add selected" over a batch — because that is where
`accept_candidates` generates missing answers one at a time.

## 2. Cost model

Let, per note:

- `N` = eligible candidates,
- `q` = fraction eventually accepted,
- `v` = fraction revealed but not accepted (looked at, then rejected),
- `c_q`, `c_a` = cost of one question / answer call,
- `I` = input tokens (source note + context), `O_q`, `O_a` = output tokens for question/answer.

### Variant A — two calls (question, then answer)

Today, answer calls happen for `q + v` of candidates:

```
today  = N·c_q + N·(q + v)·c_a
pregen = N·c_q + N·c_a
```

Extra cost = `N·c_a·(1 − q − v)`. With `c_a = 1.2 c_q`:

| Candidates whose answer is ever generated (`q + v`) | Answer calls today / 100 | Pre-generated / 100 | Total LLM cost vs today |
| --- | --- | --- | --- |
| 0.3 | 30 | 100 | **+62%** |
| 0.5 | 50 | 100 | **+38%** |
| 0.7 | 70 | 100 | **+20%** |
| 1.0 | 100 | 100 | 0% |

### Variant B — one combined call

The question and answer share one input pass:

```
today    = (I + O_q) + (q + v)·(I + O_q + O_a)
combined = I + O_q + O_a
```

Extra cost = `O_a − (q + v)·(I + O_q + O_a)`. The second term is the answer call you avoid;
the first is the extra output tokens on candidates that are never used. When answers are
short relative to the note (say `O_a` is 20–35% of an answer call), the two roughly cancel at
`q + v ≈ 0.3–0.5`. Combined generation can therefore be **near cost-neutral, sometimes
cheaper than today**, because it stops re-sending the note on every accepted answer.

What it does cost: a longer single call (question + answer output), so note processing is
slower per candidate; and coupled failure — if the question is rejected, the answer tokens
are discarded too, and a bad answer can invalidate the pair unless validation is independent.

The multiplier also depends on how many candidates a note produces. One extra answer per
candidate scales linearly with `N`, so a note with 30 candidates pays 30 answer generations.

## 3. Latency and reliability (the real win)

Assume 1–3 s per LLM call and `max_attempts = 2` (`card_generation.py:41`):

| Batch accept, no answers | Sequential LLM time |
| --- | --- |
| 10 candidates | 10–30 s (up to 60 s with retries) |
| 25 candidates | 25–75 s |
| 100 candidates (current cap) | 100–300 s |

Typical API Gateway integration timeout is ~29 s. A large "accept all" on a note whose
answers were never revealed can therefore hit a gateway timeout after some cards were
already written. That is the strongest argument for pre-generation: it moves the work out of
the request path.

Options, in order of request-path improvement:

1. **Async pre-generation after questions** — accept becomes DB-only (~10–50 ms p95), note
   processing stays unchanged, failures are retried off the request path.
2. **Inline pre-generation in the note worker** — accept is DB-only, but note processing
   doubles and `recall_status` stays `processing` longer. An answer failure can also mark
   the whole recall block failed unless isolated.
3. **Parallel answer generation inside accept** — cuts wall time by the concurrency factor,
   but still holds an HTTP request open, still costs only for accepted candidates, and adds
   concurrency/rate-limit handling to the API. A middle ground, not a fix for timeouts.

## 4. Quality and consistency

- **Same context, slightly different moment.** Questions and answers would both be grounded
  in the same note + entities + related snippets, so quality is comparable. The answer
  prompt additionally receives the question, exactly as it does today.
- **Question edits invalidate answers.** `update_suggestion` allows editing `prompt` while a
  candidate is `suggested` (`review_service.py:135-140`). A pre-generated answer would then
  describe the old question. Pre-generation needs `answer = None` + regeneration on edit, or
  it silently ships a mismatched pair.
- **Validation is unchanged.** `validate_answer` checks length and token overlap with the
  candidate/note text (`card_generation.py:120-133`); generating earlier or later does not
  change that check.
- **Combined calls couple the pair.** A single prompt that returns both fields means a
  rejected question discards a potentially good answer (and vice versa), and retries pay for
  both again. Two calls can validate the question before spending answer tokens; combined
  calls need independent validation and a sample-based quality check.
- **Staleness of the note is not a factor** if notes are immutable after processing; if they
  are editable later, both designs have the same staleness.

## 5. Failure behaviour

- **Today:** an answer failure surfaces at reveal or accept. In batch accept it fails that
  item (`ValueError`, counted as `failed`); an unexpected error can still abort the request.
- **Pre-generated:** failures happen before the user decides. That is better isolation *if*
  the state is explicit — e.g. an `answer_status` of `pending | generated | failed`, with
  retry — and *worse* if an answer failure is allowed to fail note processing or leave an
  empty answer that makes accept fail later.
- Keep the on-demand path as a fallback: if `answer` is still empty at accept, generate it
  then. Pre-generation should be an optimisation, not a new hard dependency.

## 6. What pre-generation does **not** fix

- Total LLM spend under the two-call variant (it increases); the combined variant is roughly
  neutral, but still spends on suggestions nobody opens.
- Question quality, duplicate candidates, or scoring.
- The need for idempotency and a batch contract. (Those are now in place: bulk read,
  idempotent accept, 207.)
- The card insert + candidate update transaction. (Now fixed by the `accept_recall_candidate`
  RPC, which locks the candidate and writes both atomically.)

It does simplify the accept path: no model dependency, no generation branch, easier to test
and to move into a single DB transaction later.

## 7. Recommendation

**Measure first.** The decision hinges on `q + v`, which is observable:

```sql
select status,
       count(*) filter (where answer is not null) as with_answer,
       count(*) as total
from recall_candidates
where user_id = $1
group by status;
```

- If most `carded` candidates already had an answer (reveal-before-accept is the norm), the
  latency win is small and pre-generation is mostly extra cost.
- If batch "accept all" without revealing is common, and accept p95 (or gateway timeouts)
  is a problem, pre-generate.

**If you pre-generate, prefer one combined prompt over two calls.** A single prompt that
returns `{"question": "...", "answer": "..."}` pays the note input once instead of twice, and
is close to cost-neutral (variant B). Validate the two fields independently; if the question
fails, discard both and retry. Run a small quality evaluation first — combined generation
couples answer quality to question quality, so "cheaper" is only useful if the answers are as
grounded as today's.

**Make it asynchronous.** The note job is already asynchronous via SQS, so the combined call
runs there; a second job type is not needed. Persist the pair together and only then mark the
candidate `suggested`. Fall back to the existing on-demand answer generation if the pair is
incomplete, and keep the worker's write conditional so duplicate delivery cannot overwrite a
user-triggered write.

**Rule of thumb:**

- Two-call pre-generation buys accept latency for ~`1/(q+v)` cost; at `q+v < 0.5` it is a
  1.3–1.6× increase.
- Combined pre-generation is roughly cost-neutral because it removes the repeated input
  pass; its price is longer single calls, coupled validation, and a quality risk that needs
  evaluation.
- Either way, pay for it only when accept latency/timeouts are a measured user problem, or
  when the product deliberately prioritises instant acceptance over tight LLM spend.
