---
name: intervy-scenario
description: Use when generating a language-aware company scenario for a live coding interview simulation. Invoked by intervy from-scratch mode before delegating to an interview skill.
---

# intervy-scenario — Interview Scenario Generator

## Step 1 — Generate Company Context

Before generating the story, read `context.md` (the private sub-file in this skill's folder)
and generate the company context block. The context block is presented to the candidate as
their briefing and stays in the conversation for all subsequent steps.

The story template below uses the company name, domain, stack, and pressure already
established in the context block — do not re-invent them.

---

## Randomization Contract

This skill is used DAILY. Every session must feel completely different.

**INVENT first. Use the domain pool as inspiration only, not a checklist.**

Vary across ALL of these dimensions every session:
- **Domain** — never repeat a domain used recently; prefer inventing one not on the list
- **Company stage** — seed-stage, Series A, Series B, growing, bootstrapped, enterprise spin-off
- **Problem angle** — greenfield build, legacy rewrite, scaling crisis, compliance deadline, acquisition integration, team takeover
- **Company name** — always invent a fresh, specific name that fits the domain (e.g. DropFleet, WaveDock, ArborTrade, MedQueue, FieldTrace, PulseRent, ClearTrack, NexQueue, CropLink, SeatPulse — never reuse these examples)
- **Urgency framing** — investor demo in 2 weeks, production is down, a competitor just launched, a key client is churning
- **Interview Mode** — randomly pick Mode A or Mode B each session. Vary this too — do not default to one mode.
  - **Mode A**: story only (existing behaviour)
  - **Mode B**: story + generated single-file prototype + instruction block (see Mode B Flow below)

If you find yourself defaulting to the same domain or company name pattern as a previous session, stop and invent something completely different.

---

## Domain Pool

Use as inspiration only. Prefer inventing a domain NOT on this list.

- Logistics / last-mile delivery tracking
- Jet-ski or boat rental marketplace
- Algorithmic trading / global market investments
- Restaurant order management (multi-location)
- Healthcare appointment booking and triage
- Real estate property listing and offers
- E-commerce returns and refund processing
- Event ticketing and seat reservation
- Freelancer time-tracking and invoicing
- Agricultural supply chain monitoring
- Fleet maintenance scheduling
- Pet care / veterinary appointment booking
- Coworking space desk and room booking
- Legal document review and case tracking
- Construction site safety inspection logging
- Electric vehicle charging network management
- B2B wholesale order management
- Pharmacy prescription fulfilment tracking
- Sports facility equipment rental
- Digital media asset licensing and rights management
- Food bank inventory and donation management
- Hotel housekeeping task assignment
- Parcel locker network management
- Clinical trial patient data collection
- Ski resort lift pass and equipment rental

---

## Story Template

Fill in every field. Never leave a placeholder like `[COMPANY_NAME]` — always invent a real name.

Present the story in this exact format:

---

> **Welcome.**
>
> Before we start, let me give you some context.
>
> You've just joined **[COMPANY_NAME]**, a [stage] startup in the **[DOMAIN]** space.
>
> The product is called **[PRODUCT_NAME]**. [ONE SENTENCE: what it does and who uses it.]
>
> [TWO OR THREE sentences: what's broken or missing, why the team is building this now, what the real engineering pressure is. Make it feel like a genuine business problem, not a tutorial.]
>
> Your task today is to build the core backend API for **[PRODUCT_NAME]** — from scratch, production-minded, under time pressure.

---

## Language-Aware Tailoring

The story must hint at the chosen stack. Pick ONE angle per session — vary these too.

### Python (FastAPI / Flask)

Possible angles (pick one, or invent a different one):
- Speed and async: *"The team chose Python to ship fast and integrate with existing data pipelines. They need a lightweight async API that can handle webhook bursts..."*
- Data-adjacent: *"The backend sits alongside a Python ML pipeline. The team wants a single language across the stack..."*
- Rapid iteration: *"The team needs to validate the product in 3 weeks. Python and FastAPI let them move without boilerplate..."*
- Microservice extraction: *"A monolith is being broken apart. This is the first extracted service — it must be independently deployable..."*

### Java Spring Boot

Possible angles (pick one, or invent a different one):
- Reliability: *"The team chose Spring Boot for transactional guarantees and a mature ecosystem. The service handles financial data that cannot be lost or duplicated..."*
- Enterprise integration: *"The service must integrate with a legacy ERP via REST. Spring Boot's structured layering makes it auditable and maintainable by a large team..."*
- Scale: *"The previous Python prototype can't handle the load. The team is rewriting in Spring Boot to handle thousands of concurrent requests with JPA-backed persistence..."*
- Compliance: *"A regulatory deadline is forcing a rewrite. The new service needs an auditable request log, proper transaction boundaries, and a documented API..."*

## Rules

- The story must shape entity names throughout the entire interview (a boat rental story → `/bookings`, `/vessels`, `BookingService` — never `/items`)
- Keep the story concise: 4–6 sentences total
- After outputting the story, stop — the interview skill takes over

---

## Mode B Flow

When Mode B is chosen, after outputting the story:

1. Read `scaffold.md` (the private sub-file in this skill's folder)
2. Generate and output the domain-matched single-file app following scaffold rules
3. Append the following instruction block exactly as shown, on its own line after the code:

---

> **[Interviewer note — not for the candidate]**
> Mode: RESTRUCTURE
> Phase 1 = split this single-file app into proper MVC structure.
> Round 1 coding challenge = SKIP the standard challenge. Replace with: restructure + one small
> extension (randomly pick ONE: add a query filter, add a validation constraint, add a new endpoint).
> Score Phase 1-B and the extension together as the **Round 1 Code** score.

---

Then stop. The interview skill reads this note and adjusts Phase 1 and Round 1 accordingly.
