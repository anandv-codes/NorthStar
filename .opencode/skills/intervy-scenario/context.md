# context — Company Context Generator

Private sub-file for `intervy-scenario` and `intervy-technical`. Not a standalone skill.
Read this file to generate a fresh company context for any interview session.

---

## Randomization Contract

This is called every session. Every output must feel completely different.

- INVENT everything fresh: company name, domain, product, team size, stack, pressure
- Vary company stage: pre-seed, seed, Series A, Series B, scale-up, enterprise spin-off
- Vary team size: 3–5 engineers to 200+
- Vary urgency: investor demo, compliance deadline, competitor threat, key client churning, post-acquisition integration
- Never repeat a company name or domain used recently in this conversation
- Prefer inventing a domain not in the pool below — the pool is inspiration only

---

## Domain Pool (inspiration only — prefer inventing something not on this list)

- Fintech / treasury management
- Logistics / last-mile delivery
- Healthcare appointment and triage
- Real estate marketplace
- E-commerce returns and refunds
- Event ticketing and reservations
- B2B wholesale order management
- Legal document tracking
- Fleet maintenance scheduling
- Agricultural supply chain
- Electric vehicle charging networks
- Clinical trial data collection
- Digital media asset licensing
- Coworking space management
- Pharmacy prescription fulfilment

---

## Output Format

Generate the context block and output it in this format. Fill every field — never leave a placeholder.

> **[COMPANY_NAME]** — [stage] company in the [DOMAIN] space.
> **Product:** [PRODUCT_NAME] — [one sentence: what it does and who uses it].
> **Team:** [size and structure, e.g. "12 engineers across 2 squads"].
> **Stack:** [key technologies — language, frameworks, databases, infra].
> **Pressure:** [1–2 sentences on what is urgent right now and why it matters].

---

## Rules

- Keep the block to 5–7 lines total
- Make the pressure feel real — a business deadline, a technical crisis, a competitive threat
- When called from `intervy-technical`: the stack must include the candidate's declared language/framework
- After outputting the context block, stop — the calling skill takes over
