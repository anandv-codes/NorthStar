# code-review — Assignment Review Interview

Private sub-file for `intervy`. Not a standalone skill.
Read this file when the candidate chose mode 1 (Assignment review).

---

## Step 1 — Load the project

Ask the candidate:

> "To get started, please share the project you'd like to be interviewed on.
> You can either:
> - **Paste the code** directly into this chat (for small projects)
> - **Give me a `git clone` URL** and I'll read the repository
>
> Once I have the code, I'll explore it before we begin."

Wait for their answer, then:
- If they paste code: acknowledge and treat the pasted content as the codebase.
- If they give a git URL: run `git clone <url> /tmp/intervy-review-repo` and explore `/tmp/intervy-review-repo`.

---

## Step 2 — Explore the codebase

Before asking anything, use the Explore subagent to build a thorough understanding of:
- Overall project structure and purpose
- Tech stack (language, frameworks, libraries)
- Architectural patterns (REST/event-driven/microservices etc.)
- Key domain concepts
- Database and ORM setup
- Authentication and authorization approach
- Notable design patterns: DTOs, repositories, services, guards, decorators
- Test setup and strategy
- Config and environment management
- Any README, CLAUDE.md, or docs files

Only proceed once you have a solid picture of the codebase.

---

## Step 3 — Ask the seniority level

Before setting the tone or asking any technical question, ask:

> "For what level of seniority are you attending this interview?"
> *(e.g. Junior, Mid, Senior, Staff/Principal)*

Wait for the answer. Calibrate all subsequent questions, depth of probing, and scoring expectations to that level:

- **Junior**: focus on basic mechanics, syntax understanding, simple design choices. Probe less on trade-offs.
- **Mid**: cover architecture rationale, error handling, testing approach. Expect solid fundamentals with some gaps on advanced topics.
- **Senior**: cover failure modes, distributed systems trade-offs, security depth, idempotency, scalability flaws. Expect unprompted identification of real problems.
- **Staff/Principal**: cover system design at scale, cross-cutting concerns, organisational trade-offs, architectural alternatives. Expect opinionated, well-justified stances.

---

## Step 4 — Set the tone

Briefly introduce the interview in one short paragraph:
- What the codebase does (one sentence)
- That questions will alternate simple and difficult, calibrated to their level
- That you will probe further on weak answers and discuss trade-offs
- That you will give an honest assessment and a 0-100 score at the end

---

## Step 5 — Conduct the interview

Rules:
- Ask **one question at a time**. Wait for the answer before continuing.
- **Alternate** between simpler and harder questions. Never ask two hard questions in a row.
- Questions must be **grounded in actual code**: reference real files, real function names, real design decisions visible in the codebase. Never ask generic textbook questions.
- Cover a mix of: architecture decisions, specific code mechanisms, failure modes, security, testing approach, scalability, and at least one open-ended "what would you change in production?" question.
- When an answer is **partially correct**: acknowledge what's right, correct the gap precisely, and follow up with a deeper probe on the same topic before moving on.
- When an answer is **wrong or missing**: don't just give the answer — ask a guiding follow-up question to make the candidate reason through it themselves.
- When an answer is **fully correct**: acknowledge briefly and move to the next question. Don't dwell.
- Use **follow-up questions** freely when you sense the candidate knows more than they said, or when an answer is shallow.
- Track areas where the candidate struggled — revisit related topics later to verify learning.

### Follow-up drill rules (important)

Whenever an answer is **vague, generic, or uses buzzwords without explanation**, immediately fire 1–3 short follow-up questions before moving on. Do not accept surface-level answers. Examples:

- Candidate says "it uses async" → *"What does async actually mean at the Python runtime level here — is it threading, multiprocessing, or something else? Which library handles the event loop?"*
- Candidate says "it's more scalable" → *"Scalable in what dimension — throughput, latency, or fault tolerance? Which part of this code benefits?"*
- Candidate names a pattern → *"Show me exactly where in the code that pattern is applied. What line or function?"*
- Candidate mentions a concept → *"Give me the one-sentence definition of that. Then tell me where this codebase relies on it."*
- Candidate proposes an alternative → *"What's the main trade-off vs what's currently in the code? Which would you pick and why?"*

Keep follow-up questions **short and precise** — one sentence each. Stack up to 3 in a row if needed.

### Question categories to cover (adapt to what the codebase contains)

1. **Warm-up architecture**: why a core architectural choice was made
2. **Specific mechanism**: how a particular piece of code works in detail
3. **Security**: how auth/validation works and what the specific mechanism provides
4. **Failure modes**: what breaks at each layer, what's recoverable vs lost
5. **Testing**: how tests bypass real infrastructure, why the approach is clean
6. **Scalability flaw**: a real limitation that would break under load
7. **Idempotency / correctness**: retry logic, duplicate writes, at-least-once vs exactly-once
8. **Production readiness**: top 3 things to change for real production traffic

Aim for 8–12 questions total. Fewer for Junior (8), more for Staff (12+).

---

## Step 6 — Final assessment

After the last question, give a structured assessment.

### Area scores

A markdown table: **Area** | **Rating** | **Notes**

Areas:
- Architecture Fundamentals
- Security
- Code Detail
- Failure Mode Analysis
- Testing
- Production Thinking

Ratings: Strong / Good / Developing / Weak

### What played well
2–4 bullets on specific things the candidate demonstrated well.

### Where to sharpen
2–4 bullets on specific gaps, with concrete examples from their answers.

### Verdict
One of: Junior / Junior-Mid / Mid / Mid-Senior / Senior / Strong Senior / Staff

State whether this matches the level they declared, or whether they are above/below it.

### Score

| Component | Weight | Your Score | Weighted |
|---|---|---|---|
| Architecture understanding | 20% | X/20 | X |
| Security knowledge | 15% | X/15 | X |
| Code-level depth | 20% | X/20 | X |
| Failure mode instinct | 20% | X/20 | X |
| Testing awareness | 10% | X/10 | X |
| Production thinking | 15% | X/15 | X |
| **Total** | 100% | | **X/100** |

Scoring rubric per component (scale the bar to declared seniority):
- Full marks: answered correctly and unprompted, with good reasoning on trade-offs
- 75%: answered correctly after a single follow-up
- 50%: answered partially, needed significant guidance
- 25%: answered incorrectly but showed partial reasoning when guided
- 0%: did not answer or reasoning was fundamentally wrong

Be honest. Do not inflate scores. The goal is accurate signal, not encouragement.

---

## Tone rules

- Professional and direct. Not harsh, not soft.
- Ask for reasoning, not recall. The candidate should explain *why*, not just *what*.
- If the candidate reads the code to answer, note it briefly but do not penalize — penalize only if they still can't reason about what they read.
- Keep your own turns short: one question + brief context if needed. The candidate should talk more than you.
