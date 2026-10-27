# scaffold — Single-File App Generator

Private sub-file for `intervy-scenario`. Not a standalone skill.
Read this file when Mode B is chosen to generate the single-file app.

---

## Rules for the Generated App

### Domain-matching (mandatory)

- Entity names, route paths, and field names MUST come from the story
- Example: a boat rental story → `Vessel`, `/vessels`, `rental_price` — NEVER `Item`, `/items`
- All names must be consistent with the story output from `intervy-scenario`

### Language-aware output

**Python / FastAPI:**

- Single file named `main.py`
- Must be runnable with `fastapi dev main:app`
- Use FastAPI, Pydantic BaseModel, field_validator, in-memory list as db
- Include all imports at the top

**Spring Boot:**

- Single file named `Main.java`
- All classes inlined: records or inner classes for DTOs, a controller, a service (with in-memory List), all in one file
- Must be runnable with `./mvnw spring-boot:run`
- Use proper annotations: @SpringBootApplication, @RestController, @Service, @RequestMapping, @Valid, Bean Validation

### Complexity target

The generated code must represent Round 1 difficulty:

- At least one `POST` endpoint and one `GET` endpoint
- One model/DTO with 3–4 fields
- At least one validation rule (a `field_validator` in Python, or a Bean Validation annotation in Spring Boot)
- In-memory storage only (a list or dict — no DB, no auth, no pagination)
- Correct and runnable as-is

### Deliberate bug or smell (mandatory — randomly pick ONE)

You MUST introduce exactly one of these. Vary across sessions:

1. **Wrong status code** — POST returns 200 instead of 201
2. **Missing validator** — a numeric field has no check for negative values
3. **Mutable default** (Python only) — `def f(items=[])` style bug
4. **Print statement** — `print(record)` or `System.out.println(...)` left in a route/controller handler
5. **Business logic in route handler** — validation or calculation logic directly in the endpoint method instead of a service/validator
6. **Magic value** — a hardcoded threshold (e.g. `if amount > 100`) that should be a constant or config value

### Candidate instruction (include verbatim after the code block)

After the code block, write exactly this:

> **Note:** this prototype contains at least one bug or code smell. Find it and fix it as part of your restructuring. You will not be told what it is.

---

## Output

Produce a code block with the full runnable single-file app. Then write the candidate instruction above. Then stop — the calling skill will append the Interviewer note.
