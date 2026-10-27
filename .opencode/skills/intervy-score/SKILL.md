---
name: intervy-score
description: Use when a candidate requests their score or evaluation at any point during a live coding interview simulation — mid-interview or at the end. Normalises the score relative to completed rounds only, determines seniority, and returns structured constructive feedback.
---

# intervy-score — Interview Evaluator

## Step 0 — Detect Session Type

Read the conversation context and check for the presence of `[PANEL SETUP — internal]`.

- If found → this is a multi-panel session. Read `multiple-panel-score.md` and follow it. Stop here.
- If not found → this is a single-interviewer session. Continue to Step 1 below.

---

## Overview

The candidate stopped here — by choice or because they ran out of time. That is completely fine.
Evaluate only what they completed. Never mention or penalise skipped rounds.

---

## Step 1 — Collect Scores from Context

Read the conversation and extract every score explicitly recorded by the interview skill. Build this table — mark only components that have a real score:

| Component | Max | Score | Attempted |
|---|---|---|---|
| Project Bootstrap | 10 | | |
| Round 1 Theory | 10 | | |
| Round 1 Code | 10 | | |
| Round 1.a Theory | 10 | | |
| Round 1.b Theory | 10 | | |
| Round 2 Theory | 10 | | |
| Round 2 Code | 10 | | |
| Round 3 Theory | 10 | | |
| Round 3 Code | 10 | | |
| Between-Round Probes | 10 | | |
| Round 5 Theory | 10 | | |
| Round 5 Code | 10 | | |

Only rows with a recorded score count. Ignore the rest entirely.

**Finding Between-Round Probe scores:** Search the conversation for lines matching `*[Probe scores: code=X/5 · language=Y/5]*`. Each such line is one probe invocation. Compute the score as:

```
per_probe  = code + language          (max 10 each)
avg_probe  = round(sum(per_probe) / count_of_probes)
```

Use `avg_probe` as the Between-Round Probes score (max 10). If no probe score lines exist, leave the row blank.

**Finding Standalone Questioner scores:** Search the conversation for a line matching `*[Standalone scores: X/10 · questions=N]*`. If found, use `X` directly as the Between-Round Probes score. A standalone session has no Bootstrap or Round rows — Between-Round Probes is the only scored component.

---

## Step 2 — Compute Normalised Score

```
raw          = sum of recorded scores
max_possible = sum of max points for attempted components only
final_score  = round((raw / max_possible) * 100)
```

**Example:** Bootstrap 8/10 + Round 1 Theory 7/10 + Round 1 Code 6/10 + 1 probe 6/10
→ raw = 27, max = 40 → **68/100**

---

## Step 3 — Determine Seniority

Seniority depends on BOTH score AND depth reached. A high score on easy rounds does not grant senior seniority.

| Deepest round reached | < 50% | 50–69% | 70–84% | 85–100% |
|---|---|---|---|---|
| Bootstrap only | Junior | Junior | Junior-Mid | Junior-Mid |
| Round 1 completed | Junior | Junior-Mid | Junior-Mid | Mid *(cap)* |
| Round 1.a or 1.b | Junior-Mid | Mid | Mid | Mid *(cap)* |
| Round 2 completed | Mid | Mid | Mid-Senior | Mid-Senior *(cap)* |
| Round 3 completed | Mid | Mid-Senior | Senior | Senior |
| Round 5 completed | Mid-Senior | Senior | Senior | Strong Senior |

"Deepest round reached" = the last round that has a recorded score.

---

## Step 4 — Write the Feedback

Output this structure exactly:

---

### Your Results

**Rounds completed:** [list each one by name]
**Score: X/100**
**Level: [seniority]**

---

### What you showed

2–4 bullets. Each one grounded in something concrete from their actual answers or code in this session. No generic praise — reference a real decision, a real answer, a real line of reasoning.

---

### Where to focus next

2–4 bullets. Each one names a specific gap found in this session with a direct, actionable next step. Polite but honest — do not soften gaps into useless generalities.

---

### Overall

One short paragraph. Honest, warm, forward-looking. Name the level, acknowledge what was demonstrated, point clearly at the next milestone. Should feel like a debrief from a real interviewer, not a report card.

---

## Rules

- Scores are final as recorded. Do not re-evaluate, negotiate, or reopen questions.
- Do not mention rounds the candidate did not attempt.
- Do not apologise for the scoring. Be direct.
- "What you showed" and "Where to focus" must reference evidence from this session specifically.
- If fewer than 2 components were completed, give feedback but note the assessment is limited by the amount of signal available.
