# NorthStar Recall Generation Evaluation

- Runner: `recall_generation_replay`
- Code revision: `87fcfb4`
- Cases: 4

## Summary

| Metric | Result |
| --- | ---: |
| Pair generated | 1.000 |
| Question form matched | 1.000 |
| Answer points covered | 1.000 |
| Related-note context in prompt | 1.000 |
| Multi-note cases passed | 2/2 |
| Overall pass rate | 1.000 |

## Cases

| Case | Expected form | Actual form | Pair | Points | Context | Multi-note | Pass |
| --- | --- | --- | --- | --- | --- | --- | --- |
| recall-what-definition-01 | what | what | Pass | Pass | Pass | N/A | Pass |
| recall-how-process-01 | how | how | Pass | Pass | Pass | N/A | Pass |
| recall-multi-note-how-01 | how | how | Pass | Pass | Pass | Pass | Pass |
| recall-multi-note-why-01 | why | why | Pass | Pass | Pass | Pass | Pass |

## Interpretation

This runner replays recorded model responses through the production prompt builder and validators. It is a deterministic regression check for question-form matching, answer grounding, answer-point coverage, and multi-note context plumbing. It does not measure live model quality, latency, or cost.
