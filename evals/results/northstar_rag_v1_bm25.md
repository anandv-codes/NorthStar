# NorthStar Retrieval Evaluation Result

- Runner: `bm25_smoke`
- Code revision: `3740f0a`
- Configuration: `k=5`, `k1=1.5`, `b=0.75`
- Scenario count: 40

## Summary

| Metric | Result |
| --- | ---: |
| Precision@5 | 0.379 |
| Recall@5 | 0.974 |
| Isolation failures | 0 |
| No-context checks | 1/2 |
| Conflict retrieval checks | 7/7 |

## Scenario Results

| Scenario | Query | Retrieved notes | Relevant notes | Precision | Recall | Isolation | No context | Conflict evidence |
| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| direct-owner | Who owns the Northstar onboarding redesign? | `d-project-owner`, `d-cadence` | `d-project-owner` | 0.500 | 1.000 | Pass | N/A | N/A |
| direct-storage | Where is durable work memory stored? | `d-storage-decision`, `d-release-target`, `s-migration`, `i-travel-primary`, `m-retro-action` | `d-storage-decision` | 0.200 | 1.000 | Pass | N/A | N/A |
| direct-milestone | When is the retrieval evaluation milestone due? | `d-milestone`, `s-migration`, `e-budget`, `c-retrieval-partial-old`, `c-retrieval-partial-new` | `d-milestone` | 0.200 | 1.000 | Pass | N/A | N/A |
| direct-risk | What could delay batch note processing? | `d-risk`, `s-support`, `c-launch-old`, `m-demo-scope`, `c-priority-a` | `d-risk` | 0.200 | 1.000 | Pass | N/A | N/A |
| direct-backend-owner | Who handles the FastAPI authentication migration? | `d-backend-owner`, `n-not-approved`, `d-auth-decision`, `m-audit-fix` | `d-backend-owner` | 0.250 | 1.000 | Pass | N/A | N/A |
| direct-cadence | When is the planning review held? | `d-cadence`, `c-launch-old`, `i-travel-primary`, `c-retrieval-partial-old`, `e-date` | `d-cadence` | 0.200 | 1.000 | Pass | N/A | N/A |
| direct-release-target | Who is the first work-memory beta for? | `d-release-target`, `d-storage-decision`, `n-excluded`, `c-proposal`, `s-migration` | `d-release-target` | 0.200 | 1.000 | Pass | N/A | N/A |
| direct-auth | What happens after a successful refresh request? | `d-auth-decision`, `c-proposal`, `s-cleanup`, `m-audit-fix`, `m-hiring-timeline` | `d-auth-decision` | 0.200 | 1.000 | Pass | N/A | N/A |
| exact-incident | What caused INC-482? | `e-incident-482` | `e-incident-482` | 1.000 | 1.000 | Pass | N/A | N/A |
| exact-budget | What is the evaluation tooling budget cap? | `e-budget`, `d-milestone`, `s-migration` | `e-budget` | 0.333 | 1.000 | Pass | N/A | N/A |
| exact-build | What changed in build 2026.02.03.7? | `e-build`, `e-date`, `c-vendor-reopened` | `e-build` | 0.333 | 1.000 | Pass | N/A | N/A |
| exact-contract | What notes API contract version requires text? | `e-contract-v2`, `c-vendor-reopened`, `c-vendor-complete`, `c-date-a`, `c-risk-high` | `e-contract-v2` | 0.200 | 1.000 | Pass | N/A | N/A |
| exact-date | When is the architecture review in 2026? | `e-date`, `m-hiring-timeline`, `e-build`, `c-retrieval-partial-old`, `d-storage-decision` | `e-date` | 0.200 | 1.000 | Pass | N/A | N/A |
| exact-flag | What does RAG_GUARDRAIL_V2 control? | `e-flag`, `n-excluded`, `e-contract-v2` | `e-flag` | 0.333 | 1.000 | Pass | N/A | N/A |
| semantic-sync | How will the team clear blockers every day? | `s-sync`, `m-proposal-owner`, `d-cadence`, `d-auth-decision`, `n-no-deploy` | `s-sync` | 0.200 | 1.000 | Pass | N/A | N/A |
| semantic-cleanup | What should happen to old prompt logs? | `s-cleanup`, `c-risk-low`, `c-risk-high` | `s-cleanup` | 0.333 | 1.000 | Pass | N/A | N/A |
| semantic-design | What dashboard style supports quick work review? | `s-design`, `c-priority-a`, `c-priority-b`, `c-retrieval-partial-old`, `e-date` | `s-design` | 0.200 | 1.000 | Pass | N/A | N/A |
| semantic-support | How should failed note processing be documented for users? | `s-support`, `d-risk`, `c-launch-old`, `m-demo-scope`, `c-priority-a` | `s-support` | 0.200 | 1.000 | Pass | N/A | N/A |
| semantic-migration | What must happen to older notes before retrieval testing? | `s-migration`, `m-hiring-dependency`, `c-risk-high`, `c-priority-a`, `c-priority-b` | `s-migration` | 0.200 | 1.000 | Pass | N/A | N/A |
| semantic-knowledge | Why write down the retrieval architecture? | `d-storage-decision`, `e-date`, `m-hiring-timeline`, `c-retrieval-partial-old`, `d-milestone` | `s-knowledge` | 0.000 | 0.000 | Pass | N/A | N/A |
| multi-retro | What did the retrospective find and what action follows? | `m-retro-context`, `m-retro-action` | `m-retro-context`, `m-retro-action` | 1.000 | 1.000 | Pass | N/A | N/A |
| multi-hiring | When can backend engineer interviews begin and what must happen first? | `m-hiring-dependency`, `m-hiring-timeline`, `d-release-target` | `m-hiring-timeline`, `m-hiring-dependency` | 0.667 | 1.000 | Pass | N/A | N/A |
| multi-demo | What is in the stakeholder demo and what is excluded? | `m-demo-scope`, `m-demo-risk` | `m-demo-scope`, `m-demo-risk` | 1.000 | 1.000 | Pass | N/A | N/A |
| multi-observability | Who owns the observability proposal and what must it include? | `m-proposal-owner`, `m-proposal-requirement`, `n-excluded`, `d-project-owner`, `m-hiring-dependency` | `m-proposal-requirement`, `m-proposal-owner` | 0.400 | 1.000 | Pass | N/A | N/A |
| multi-security | What did the security audit find and what is the fix plan? | `m-audit-fix`, `m-audit-finding`, `n-not-approved` | `m-audit-finding`, `m-audit-fix` | 0.667 | 1.000 | Pass | N/A | N/A |
| conflict-launch | When is the mobile launch planned? | `c-launch-old`, `c-launch-new`, `c-date-b` | `c-launch-old`, `c-launch-new` | 0.667 | 1.000 | Pass | N/A | Pass |
| conflict-vendor | Is the vendor API contract follow-up complete? | `c-vendor-complete`, `c-vendor-reopened`, `n-vendor-incomplete`, `e-contract-v2`, `s-support` | `c-vendor-complete`, `c-vendor-reopened` | 0.400 | 1.000 | Pass | N/A | Pass |
| conflict-vector-store | Should the beta use a managed vector database? | `c-proposal`, `c-proposal-approved`, `n-excluded`, `s-design`, `d-release-target` | `c-proposal`, `c-proposal-approved` | 0.400 | 1.000 | Pass | N/A | Pass |
| conflict-priority | What should the next sprint prioritize? | `c-priority-a`, `c-priority-b`, `m-retro-context`, `m-retro-action` | `c-priority-a`, `c-priority-b` | 0.500 | 1.000 | Pass | N/A | Pass |
| conflict-compliance-scope | When is the compliance review? | `c-date-a`, `c-date-b`, `c-retrieval-partial-old`, `e-date`, `d-cadence` | `c-date-a`, `c-date-b` | 0.400 | 1.000 | Pass | N/A | Pass |
| conflict-risk | How severe is the prompt logging risk? | `c-risk-low`, `c-risk-high`, `s-cleanup`, `d-risk` | `c-risk-low`, `c-risk-high` | 0.500 | 1.000 | Pass | N/A | Pass |
| conflict-rewrite-experiment | Is the retrieval rewrite experiment ready for review? | `c-retrieval-partial-old`, `c-retrieval-partial-new`, `e-date`, `c-date-a`, `c-date-b` | `c-retrieval-partial-old`, `c-retrieval-partial-new` | 0.400 | 1.000 | Pass | N/A | Pass |
| negation-production | Is the production deployment approved? | `n-not-approved`, `n-vendor-incomplete` | `n-not-approved` | 0.500 | 1.000 | Pass | N/A | N/A |
| negation-friday | Can the Lambda worker deploy on Friday? | `n-no-deploy`, `m-proposal-owner`, `m-hiring-dependency`, `e-incident-482` | `n-no-deploy` | 0.250 | 1.000 | Pass | N/A | N/A |
| negation-vendor | Is the data-retention vendor review complete? | `n-vendor-incomplete`, `s-cleanup`, `s-support`, `c-vendor-complete`, `c-vendor-reopened` | `n-vendor-incomplete` | 0.200 | 1.000 | Pass | N/A | N/A |
| negation-cohort | Are external contractors in the beta cohort? | `n-excluded`, `d-release-target`, `c-proposal`, `c-proposal-approved` | `n-excluded` | 0.250 | 1.000 | Pass | N/A | N/A |
| no-context-parking | What is the office parking policy? | `e-flag` | None | N/A | N/A | Pass | Fail | N/A |
| no-context-benefits | What is the dental benefits provider? | None | None | N/A | N/A | Pass | Pass | N/A |
| isolation-travel | When does my Seattle work trip start? | `i-travel-primary`, `n-excluded`, `d-release-target`, `m-retro-action`, `s-design` | `i-travel-primary` | 0.200 | 1.000 | Pass | N/A | N/A |
| isolation-health | When should I schedule my annual eye exam? | `i-health-primary`, `i-travel-primary` | `i-health-primary` | 0.500 | 1.000 | Pass | N/A | N/A |

## Interpretation

This is a deterministic BM25 smoke baseline over synthetic notes. It measures retrieval only; it does not evaluate generated answers, claim support, conflict resolution wording, latency, or model cost.
