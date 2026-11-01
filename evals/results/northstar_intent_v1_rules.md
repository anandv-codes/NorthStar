# NorthStar Intent Evaluation

- Runner: `intent_rules`
- Code revision: `e32e27c`
- Configuration: `threshold=0.42`, `margin=0.03`, `top_examples=2`
- Cases: 48
- Accuracy: 0.792
- Action precision: 1.000

## Per-label

| Label | Precision | Recall | F1 | Support |
| --- | ---: | ---: | ---: | ---: |
| conversation | 0.000 | 0.000 | 0.000 | 10 |
| note_content | 1.000 | 1.000 | 1.000 | 14 |
| note_status | 1.000 | 1.000 | 1.000 | 14 |
| action | 1.000 | 1.000 | 1.000 | 10 |

## Confusion

| Expected | Predicted | Count |
| --- | --- | ---: |
| conversation | ambiguous | 10 |
| note_content | note_content | 14 |
| note_status | note_status | 14 |
| action | action | 10 |

## Cases

| Expected | Predicted | Confidence | Text |
| --- | --- | ---: | --- |
| conversation | ambiguous | 0.35 | morning |
| conversation | ambiguous | 0.35 | hey there |
| conversation | ambiguous | 0.35 | thanks, that's useful |
| conversation | ambiguous | 0.35 | nice one |
| conversation | ambiguous | 0.35 | what are you able to help with |
| conversation | ambiguous | 0.35 | can you help me |
| conversation | ambiguous | 0.35 | appreciate it |
| conversation | ambiguous | 0.35 | ok got it |
| conversation | ambiguous | 0.35 | hello again |
| conversation | ambiguous | 0.35 | are you online |
| note_content | note_content | 0.84 | what did I capture in the pricing call |
| note_content | note_content | 0.89 | show me what I wrote about the incident |
| note_content | note_content | 0.77 | can you recap yesterday's notes |
| note_content | note_content | 0.77 | what's my earlier context on the billing migration |
| note_content | note_content | 0.89 | find anything I noted about onboarding |
| note_content | note_content | 0.84 | what was my takeaway from the design review |
| note_content | note_content | 0.77 | pull up what I said about the datafix |
| note_content | note_content | 0.89 | what did I learn in the SDE interview prep |
| note_content | note_content | 0.77 | do I have notes on the vendor decision |
| note_content | note_content | 0.89 | what did I record during the client sync |
| note_content | note_content | 0.77 | give me my notes about the API rollout |
| note_content | note_content | 0.77 | what have I written about analytics |
| note_content | note_content | 0.89 | summarize my day |
| note_content | note_content | 0.84 | what was discussed about hiring |
| note_status | note_status | 0.83 | is the pricing task finished |
| note_status | note_status | 0.83 | did the client sync get scheduled |
| note_status | note_status | 0.83 | what work is left this week |
| note_status | note_status | 0.83 | anything blocked right now |
| note_status | note_status | 0.83 | has the billing migration been completed |
| note_status | note_status | 0.83 | which items are still in progress |
| note_status | note_status | 0.83 | what did I wrap up today |
| note_status | note_status | 0.83 | are there unfinished tasks |
| note_status | note_status | 0.83 | what's the state of the rollout |
| note_status | note_status | 0.83 | did I close the auth item |
| note_status | note_status | 0.83 | what's waiting on the vendor |
| note_status | note_status | 0.83 | which questions remain open |
| note_status | note_status | 0.83 | is the interview prep done |
| note_status | note_status | 0.83 | what have I not completed |
| action | action | 0.87 | please add a task to ping priya |
| action | action | 0.87 | remind me to book the room |
| action | action | 0.87 | can you mark the migration task done |
| action | action | 0.87 | complete the pricing follow-up |
| action | action | 0.87 | reopen the vendor decision task |
| action | action | 0.87 | start the hiring task |
| action | action | 0.87 | set the rollout task to in progress |
| action | action | 0.87 | close out the budget item |
| action | action | 0.87 | add a todo for the design review |
| action | action | 0.87 | create a task for the client sync |
