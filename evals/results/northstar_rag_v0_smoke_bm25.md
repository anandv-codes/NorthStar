# NorthStar Retrieval Evaluation Result

- Runner: `bm25_smoke`
- Code revision: `a7770a7`
- Configuration: `k=5`, `k1=1.5`, `b=0.75`
- Scenario count: 8

## Summary

| Metric | Result |
| --- | ---: |
| Precision@5 | 0.786 |
| Recall@5 | 1.000 |
| MRR@5 | 0.929 |
| Isolation failures | 0 |
| No-context checks | 1/1 |
| Conflict retrieval checks | 2/2 |

## Scenario Results

| Scenario | Query | Retrieved notes | Relevant notes | Precision | Recall | Reciprocal rank | Isolation | No context | Conflict evidence |
| --- | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |
| launch-conflict | When is the mobile launch planned? | `launch-august`, `launch-september` | `launch-august`, `launch-september` | 1.000 | 1.000 | 1.000 | Pass | N/A | Pass |
| atlas-owner | Who owns the Project Atlas data migration? | `atlas-owner`, `atlas-budget` | `atlas-owner` | 0.500 | 1.000 | 1.000 | Pass | N/A | N/A |
| atlas-budget | What is the Project Atlas budget cap? | `atlas-budget`, `atlas-owner` | `atlas-budget` | 0.500 | 1.000 | 1.000 | Pass | N/A | N/A |
| release-status | What is blocking the release? | `release-blocked` | `release-blocked` | 1.000 | 1.000 | 1.000 | Pass | N/A | N/A |
| vendor-status | Did I finish the vendor API contract follow-up? | `vendor-open`, `vendor-complete` | `vendor-open`, `vendor-complete` | 1.000 | 1.000 | 1.000 | Pass | N/A | Pass |
| auth-decision | What happens after a successful refresh token request? | `auth-refresh` | `auth-refresh` | 1.000 | 1.000 | 1.000 | Pass | N/A | N/A |
| no-context | What is the office parking policy? | None | None | N/A | N/A | N/A | Pass | Pass | N/A |
| isolation-launch | What mobile launch date did I decide? | `launch-august`, `launch-september` | `launch-september` | 0.500 | 1.000 | 0.500 | Pass | N/A | N/A |

## Interpretation

This is a deterministic BM25 smoke baseline over synthetic notes. It measures retrieval only; it does not evaluate generated answers, claim support, conflict resolution wording, latency, or model cost.
