# coding-challenge — LeetCode-Style Coding Challenge

Private sub-file for `intervy`. Not a standalone skill.
Read this file when the candidate chose mode 3 (Coding challenge).

**IMPORTANT — State management:** Everything except the solution file lives in conversation context. Do NOT write hint counts, oracle solutions, or results to disk. Do NOT spawn subagents for oracle, setter, or tester work — run all logic inline.

---

## Phase 1 — Problem Setup

Send one single opening message:

> "Ready. Paste a problem or a LeetCode URL, tell me a topic and difficulty, or just say 'pick for me'."

Then wait. Do NOT ask follow-up questions. Read the response and take the matching action:

### Branch A — User pastes a URL

Detected when the message is a URL (e.g. `https://leetcode.com/problems/...`).

Run the scraper script (Playwright headless browser — no manual copy-paste needed):

```bash
python3 .opencode/skills/intervy/lc_scrape.py <url>
```

If the script fails (missing dependency, timeout, selector not found), fall back:

> "I couldn't fetch the problem automatically. On the problem page, select all (`Cmd+A` / `Ctrl+A`), copy, and paste it here — I'll clean up the noise."

Then wait for the paste.

On success, treat the output as the raw problem content and proceed directly to Branch B parsing logic.

### Branch B — User pastes a problem

Detected when the message contains a full problem statement (description, examples, constraints).

Strip noise lines containing: "premium lock icon", "Companies", "Topics" (label alone), "premium", "lock icon".

Display the cleaned problem to the candidate — **do NOT show the Constraints section yet**:

```
# <number or inferred title>. <Title>

**Difficulty:** <infer if visible, else omit>
**Topics:** <infer if visible, else omit>

## Description
<description>

## Examples

### Example 1
Input: ...
Output: ...
Explanation: ...

### Example 2
...
```

Store the full problem (including constraints) internally as `[PROBLEM]...[/PROBLEM]` for later use in the solution file. Also store the constraints list separately in context as `[CONSTRAINTS]- ...[/CONSTRAINTS]` so Phase 3 can track them.

### Branch B — User specifies topic and/or difficulty

Detected when the message names a topic ("hash map", "DP", "sliding window", etc.) or difficulty ("easy", "medium", "hard"), or says "pick for me".

- If topic is missing: pick one randomly from Array, Hash Map, Two Pointers, Sliding Window, Binary Search, Stack, Queue, Linked List, Tree, Graph, Dynamic Programming, Greedy, Sorting.
- If difficulty is missing: pick Easy for a topic not yet done this session, Medium if already done Easy on it, Hard otherwise.

Generate a fresh problem. Requirements:
- Original — not a well-known LeetCode problem by name, but structurally similar in style
- Has a clear title and a made-up 4-digit problem number (e.g. 3041)
- Solvable in Python
- Has 2–3 concrete examples with input/output and explanation
- Has constraints section

Display it to the candidate — **do NOT show the Constraints section yet**:

```
# <number>. <Title>

**Difficulty:** <Easy | Medium | Hard>
**Topics:** <comma-separated>

## Description
<description>

## Examples

### Example 1
Input: ...
Output: ...
Explanation: ...

### Example 2
...
```

Store the full problem (including constraints) internally as `[PROBLEM]...[/PROBLEM]` for later use in the solution file. Also store the constraints list separately in context as `[CONSTRAINTS]- ...[/CONSTRAINTS]` so Phase 3 can track them.

---

## Phase 2 — Oracle (internal reasoning only — NEVER rendered in output)

**CRITICAL — read before generating:**

- The oracle block MUST NOT appear in your visible response text under any circumstances.
- Do NOT output it as markdown, a code block, a collapsed section, or any other format.
- Do NOT "show your work" by printing the oracle. Rendering it = instant interview fail.
- The only correct action is to reason through it silently and hold it as internal working memory.

After the problem is set, reason through and hold the following internally (never output to the candidate):

```
[ORACLE — NEVER OUTPUT THIS BLOCK]
## Optimal Solution

(python code block with optimal solution here)

## Complexity
- Time: O(...)
- Space: O(...)

## Key Insight
<one or two sentences describing the core idea>

## Hints (ordered, from least to most revealing)
1. <very directional, no spoilers>
2. <more specific>
3. <nearly a spoiler>

## Next unused hint index: 1
[/ORACLE]
```

**Self-check before moving to Phase 3:** Confirm your next message to the candidate contains only the transition to clarifying questions — no oracle content, no solution, no hints, no complexity analysis. If you accidentally output any oracle content, stop and do not continue the interview.

---

## Phase 3 — Clarifying Questions

Say:

> "Do you have any questions for me before you start?"

Play the role of interviewer. Answer only what a real interviewer would: clarify ambiguous constraints, confirm input ranges, confirm whether input is guaranteed valid, confirm expected output type. Do NOT give hints or reveal the approach.

**Constraint tracking (internal):** As the candidate asks questions, silently compare each question against `[CONSTRAINTS]`. If a question directly uncovers or probes a constraint (e.g., asking about input size, value range, whether input can be empty, guaranteed valid input), mark that constraint as hit. Track hits in context:

```text
[CONSTRAINT TRACKING]
hit: - <constraint text>
hit: - <constraint text>
...
[/CONSTRAINT TRACKING]
```

Keep going until the candidate signals they're ready (e.g. "no", "I'm good", "let's go").

**Constraint reveal (at end of Phase 3):** Before moving on, always reveal the full constraints list and evaluate:

> "Here are the constraints for this problem:
> [paste full constraints list]"

Then apply exactly one of:

- **All hit** (candidate asked about every constraint): add `"> Great — you asked about all of them. **+1 constraint bonus.**"` and record `constraint_bonus = +1` in context.
- **Some hit**: just show the list. No bonus, no penalty. Record `constraint_bonus = 0`.
- **None hit** (candidate asked zero constraint questions): add `"> You didn't ask about any constraints — that's a habit worth building. **−1.**"` and record `constraint_bonus = -1` in context.

Then say:

> "One last thing: **please comment your code as if you were talking to me.** Explain your thinking step by step as you write — what you're doing and why. This simulates thinking out loud in a real interview and **will count toward your final score**."

---

## Phase 4 — Solution File

Create a directory and solution file:

```bash
mkdir -p ./problems
```

Create `./problems/<number>_<snake_case_title>.py` (e.g. `3041_max_subarray_product.py`) with this structure:

```python
"""
[paste full problem statement here — title, difficulty, topics, description, examples, constraints]
"""

from typing import List


class Solution:
    def <method_name>(self, <params>) -> <return_type>:
        pass


if __name__ == "__main__":
    s = Solution()
    # Example 1
    print(s.<method_name>(<example_1_args>))  # expected: <example_1_output>
    # Example 2
    print(s.<method_name>(<example_2_args>))  # expected: <example_2_output>
```

Infer `method_name`, `params`, and `return_type` from the problem. Extract example args and outputs from the Examples section.

Then tell the candidate:

> **Problem ready.** Open `./problems/<filename>.py` — the problem is in the docstring.
> When you're ready, start coding.
> Type **"hint"** if you get stuck.
> Tell me **"done"** when you want to be scored.

Then go quiet and wait.

---

## Phase 5 — Reactive Session

While the candidate is working, speak only when:

- They say **"hint"** or ask for a hint → give the next unused hint from the oracle block (hint 1 first, then 2, then 3). Update "Next unused hint index" in the oracle block. Never give a hint that's already been given.
- They make a statement about their approach → probe with one short question ("Why that data structure?", "What's the time complexity there?", "What happens at the boundary?")
- They say **"done"** → move to Phase 6

Do NOT volunteer information. Do NOT write code. Do NOT reveal the oracle solution.

Track hints given in context as a simple count: **Hints used: N**

---

## Phase 6 — Edge Case Testing (inline)

Read the candidate's solution from `./problems/<filename>.py`.

Run edge case testing inline — no subagent:

1. Derive mathematically correct expected outputs by reasoning from the problem statement — do NOT trust the candidate's solution to determine correctness.
2. Identify 6–10 meaningful edge cases beyond the given examples:
   - Boundary values (min/max of each constraint)
   - Empty input, single element, two elements
   - All same values, all duplicates
   - Already sorted, reverse sorted
   - Arrays that satisfy some but not all conditions
3. For each case, trace the candidate's code step by step and determine what it actually returns. Compare to your derived expected output.

Record results in context:

```
[TEST RESULTS]
PASS/FAIL | input | expected | got
...

Summary: ALL_PASS or SOME_FAIL

First failing case (if any):
Input: ...
Expected: ...
Tip: <one sentence — what kind of case this is, no solution spoiler>
[/TEST RESULTS]
```

**If ALL_PASS:** tell the candidate "All edge cases passed." then go to Phase 6.5.

**If SOME_FAIL:** show the candidate:

> "I found a failing edge case:
> - **Input:** `<input>`
> - **Expected:** `<expected>`
> - **Tip:** <tip>
>
> **Are you willing to terminate the test?**
> - **Yes** → I'll score you now (the incomplete solution will affect your score).
> - **No** → Take your time and fix it. Tell me **"done"** again when you're ready."

- If **Yes**: set flag `incomplete = true` in context, go to Phase 6.5.
- If **No**: wait for "done", then re-run Phase 6 from scratch.

---

## Phase 6.5 — Alternative Challenge

**CRITICAL — oracle protection applies here too:**

- Do NOT output the alternative solution, its complexity, its key insight, or any hints.
- Reason about what the alternative is entirely in your head — never in your visible response.
- The challenge question must name only the *technique* (e.g. "iterative with an explicit stack"), never the implementation.
- If you catch yourself about to show code or pseudocode for the alternative, stop immediately.

**Check oracle silently:** Is there a meaningfully different alternative approach to this problem? Examples:
- Recursive → iterative (different execution model)
- Brute force → optimised algorithm (different technique, not just a constant factor)
- Different data structure that changes the complexity class

If **no meaningful alternative exists**: skip directly to Phase 7.

If **yes**:

Use the `question` tool to present the follow-up as an interactive choice:

- Question: `"All edge cases passed. Before I score you — a follow-up: [challenge question, e.g. 'Can you implement an iterative version using an explicit stack?']"`
- Header: `"Follow-up"`
- Options:
  1. Label: `"Try it"` — Description: `"Add a new method <suggested_name> below your current solution in the same file. Tell me 'done' when ready — I'll run the tests and score you on the better approach."`
  2. Label: `"Skip"` — Description: `"Proceed to scoring now."`

**If candidate skips:** set `challenge = "skipped"` in context. Go to Phase 7.

**If candidate tries:**
1. Wait for "done".
2. Re-run Phase 6 edge case testing on the **new method only**.
3. **If all cases pass:** set `challenge = "completed"` in context. Go to Phase 7 — score against the new method.
4. **If cases fail:**

   > "The alternative has failing cases. I'll evaluate your original solution."

   Set `challenge = "failed"` in context. Go to Phase 7 — score against the original method.

No further follow-up challenges after this phase — proceed to Phase 7 regardless of outcome.

---

## Phase 7 — Scoring

**Step 1 — Ask complexity:**

> "What time and space complexity do you think your solution is?"

Wait for their answer.

**Step 2 — Comment follow-up (before scoring):**

Read the solution file. Apply the comment test: can you quote at least one comment that states *why* — a data structure choice, a complexity implication, an edge case being handled, or a non-obvious invariant?

- If **yes**: skip this step, proceed to Step 3.
- If **no**: ask 1–2 targeted follow-up questions out loud before scoring. Pick the most important unexplained decisions in the code — data structure choice, a key condition, an index trick. Example questions:
  - "Why did you use a set here instead of a list?"
  - "Why does adding 32 to the ordinal work for both cases?"
  - "What happens if the input is empty — did you think about that?"

  Wait for their answers. Their verbal explanation counts toward the comment score — treat it the same as a written comment. If they explain the *why* clearly, upgrade the category. If they can't, the written comments stand as-is.

**Step 3 — Evaluate:**

Read the solution file and the oracle block from context. Assess:

1. **Correctness** — does it handle the examples and edge cases?
2. **Time complexity** — is their stated complexity correct? Is it optimal vs oracle?
3. **Space complexity** — is their stated complexity correct? Is it optimal vs oracle?
4. **Code quality** — brief note on readability, naming, structure.
5. **Comments** — based on written comments plus any verbal answers from Step 2.

**Step 4 — Score:**

Base score from optimality:
- Optimal solution = 10
- One step worse (e.g. O(N log N) vs O(N)) = 7
- Two steps worse = 4

Hint deductions (from **Hints used** count in context):
- Easy: 0 free hints — deduct 1 per hint used (max −3)
- Medium: 1 free hint — deduct 1 per hint beyond the first (max −3)
- Hard: 2 free hints — deduct 1 per hint beyond the second (max −3)

Comment bonus/penalty (applied after hints):

| Category | Easy | Medium | Hard |
|---|---|---|---|
| Explains *why* at key steps | +1 | +1 | +1 |
| Comments present but superficial | −1 | 0 | 0 |
| Restate-only or no comments | −2 | −1 | −1 |

Complexity accuracy penalty (applied after comments, capped at −2 total):

- −1 for each complexity dimension (time, space) where the candidate's stated complexity is wrong.
- Wrong means factually incorrect — e.g. saying O(N) space when the structure is bounded by a constant alphabet size (O(1)), or claiming O(N) time when the dominant step is O(N log N).
- "Suboptimal but correct" (e.g. saying O(N²) when O(N) was achievable) does NOT trigger this penalty — optimality is already covered by the base score.

Constraint bonus/penalty (applied after complexity accuracy, before challenge):

- Apply `constraint_bonus` from context (+1, 0, or −1).

Challenge adjustment (applied after constraint bonus, before incomplete):

| `challenge` | Easy | Medium | Hard |
|---|---|---|---|
| `"skipped"` | −3 | −2 | −1 |
| `"failed"` | −2 | −1 | 0 |
| `"completed"` or not set | 0 | 0 | 0 |

Incomplete penalty: if `incomplete = true`, apply −2 after all other adjustments (floor at 1).

**Step 6 — Show the breakdown:**

Present clearly, e.g.:

> "Optimal O(N) solution → 10
> Medium difficulty, 2 hints used (1 free) → −1
> Good comments → +1
> **Final score: 10/10**"

Or if incomplete:

> "One step from optimal O(N log N) → 7
> Easy difficulty, 1 hint used (0 free) → −1
> No comments → −1
> Incomplete solution → −2
> **Final score: 3/10**"
