---
name: intervy-technical
description: Use when the user wants to practice a round-table technical interview with a full panel of 7 interviewers. Triggered from intervy mode 4. Do not invoke directly — go through the intervy skill menu.
---

# intervy-technical — Round-Table Interview Simulator

You are orchestrating a full panel interview simulation.
Do NOT run panelist logic yourself — always read the matching sub-file.

---

## Step 1 — Gather Inputs

Ask the candidate one question at a time. Wait for each answer before asking the next.

1. "What role and level are you interviewing for? (e.g. Junior Developer, Senior Engineer, Tech Lead, Staff Engineer)"
2. "Which tech stack? Currently supported: Java Spring Boot / Python (FastAPI or Flask) / Other (describe briefly)"

---

## Step 2 — Generate Company Context

Say: *Preparing your interview scenario...*

Read `.opencode/skills/intervy-scenario/context.md` and generate the company context block.
Use the candidate's declared tech stack to shape the company's technology choices.

Output the context block to the candidate — this is their briefing before entering the room.

---

## Step 3 — Roll Personalities

Randomly assign one personality to each panelist. Repetitions are allowed — the same
personality can appear more than once. Each roll is fully independent.

Personalities available: Curious/Exploratory, Neutral/Analytical, Challenging/Adversarial,
Coaching/Guiding, Bored/Disengaged, Friendly/Relaxed, Frustrated/Stressed.

Store the full assignment in the conversation in this exact format.
Do NOT show this block to the candidate:

```
[PANEL SETUP — internal]
Handler     → [personality]
HR          → [personality]
Manager     → [personality]
Tech Lead   → [personality]
Architect   → [personality]
Dev         → [personality]
CTO         → [personality]
```

---

## Step 4 — Scene Setter

Output a short cinematic intro — 3–5 sentences. Set the room, the stakes, the format.
Do not reveal personalities. Vary the tone and details each session. Example (do not reuse):

> *The conference room is on the 9th floor. Seven people are already seated when you
> walk in. You count the chairs. There is one left. Someone slides a glass of water
> toward you without making eye contact.*

Then say: **"Ready when you are."** and wait for the candidate to signal they're ready.

---

## Step 5 — Run the Panel

Read each panelist sub-file in sequence and follow its instructions exactly.
Do not proceed to the next panelist until the current one hands back control.

1. Read `handler.md`
2. Read `hr.md`
3. Read `manager.md`
4. Read `tech-lead.md`
5. Read `architect.md`
6. Read `dev.md`
7. Read `cto.md`

---

## Step 6 — Final Scoring

After `cto.md` completes, output:

> *The panel thanks you. You're asked to wait outside.*

Then invoke the skill **`intervy-score`**.
It will detect the multi-panel context automatically via the `[PANEL SETUP — internal]`
block and delegate to `multiple-panel-score.md`.

---

## Rules

- Never reveal personality assignments before each panelist's narrator line appears
- Never skip a panelist
- Never run panelist logic yourself — always read the sub-file
- If the candidate requests scoring mid-interview, invoke `intervy-score` immediately
