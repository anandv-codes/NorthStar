# multiple-panel-score — Panel Verdict Scorer

Private sub-file for `intervy-score`. Not a standalone skill.
Read this file when a multi-panel interview session is detected.

---

## Step 1 — Collect Scores

Read the conversation and extract every panelist score recorded in the format:
`[Panelist score: X/10 — "opinion"]`

Build this table — include only panelists who have a recorded score:

| Panelist | Raw (0–10) | Weight | Weighted pts | Opinion |
| --- | --- | --- | --- | --- |
| HR | | 0.5 | | |
| Manager | | 1.0 | | |
| Tech Lead | | 4.0 | | |
| Architect | | 2.0 | | |
| Dev | | 1.0 | | |
| CTO | | 1.5 | | |

Weighted pts = raw × weight.

Max weighted pts per panelist (for reference):

| Panelist | Max pts |
| --- | --- |
| HR | 5 |
| Manager | 10 |
| Tech Lead | 40 |
| Architect | 20 |
| Dev | 10 |
| CTO | 15 |
| **Total** | **100** |

If a panelist was skipped (no score in context), exclude them entirely.
Note any skipped panelists in the report.

---

## Step 2 — Compute Final Score

```
final_score = sum of all weighted pts
```

If panelists were skipped, normalise:

```
final_score = round((sum of weighted pts / sum of max pts for present panelists) * 100)
```

---

## Step 3 — Determine Seniority

| Score | Level |
| --- | --- |
| < 40 | Junior |
| 40–54 | Junior-Mid |
| 55–69 | Mid |
| 70–79 | Mid-Senior |
| 80–89 | Senior |
| 90–100 | Strong Senior |

---

## Step 4 — Output the Panel Verdict

Output exactly this structure. Fill every section — no placeholders:

---

```
─────────────────────────────────────────
  PANEL VERDICT
─────────────────────────────────────────

Score: XX/100
Level: [seniority level]

─── What the panel said ─────────────────

Handler   ([personality]) — introduced the session, no score
HR        ([personality]) — [opinion from context, in HR's voice]
Manager   ([personality]) — [opinion from context, in Manager's voice]
Tech Lead ([personality]) — [opinion from context, in Tech Lead's voice]
Architect ([personality]) — [opinion from context, in Architect's voice]
Dev       ([personality]) — [opinion from context, in Dev's voice]
CTO       ([personality]) — [opinion from context, in CTO's voice]

─── Strengths ───────────────────────────

2–3 bullets. Each grounded in a specific answer, decision, or reasoning moment
from this session. No generic praise — reference real moments.

─── Where to focus ──────────────────────

2–3 bullets. Each names a specific gap found in this session with a direct,
actionable next step. Polite but honest — do not soften gaps into generalities.

─── Overall ─────────────────────────────

One short paragraph. Honest, warm, forward-looking. Names the level, acknowledges
what was demonstrated, points clearly at the next milestone.
─────────────────────────────────────────
```

---

## Rules

- Scores are final as recorded. Do not re-evaluate or reopen questions.
- Opinions must be in each panelist's voice, coloured by their assigned personality.
  A bored panelist's opinion is terse and unimpressed. A coaching one is warm but honest.
- Strengths and gaps must reference evidence from this session specifically.
- Do not mention panelists who did not participate.
- Handler always appears in the panel section but has no score and no opinion beyond their role.
