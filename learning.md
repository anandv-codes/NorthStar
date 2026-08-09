# Learning: NorthStar retrieval + chat workflow

## Big picture

NorthStar now combines retrieval, chat persistence, and agentic orchestration scaffolding.
The current system turns a user message into:

1. stored conversation state
2. context from memory and retrieval
3. an assistant response
4. updated thread history for the next turn

## Implemented retrieval flow

1. Validate and normalize the query.
2. Load a small slice of recent memory for rewrite context.
3. Score query quality.
4. If the query is good enough, ask Gemini for one rewrite.
5. Check rewrite risks:
   - missing numbers
   - negation loss
   - semantic drift
   - empty rewrite
6. Retrieve candidates from multiple sources.
7. Fuse candidates with RRF.
8. Optionally rerank the fused list.

## Retrieval sources

- Dense retrieval: existing Chroma-based semantic search.
- Sparse retrieval: BM25 over the current user’s notes.

## Why hybrid retrieval

- Dense search is good for meaning.
- BM25 is good for exact terms, IDs, task names, and rare words.
- RRF keeps both signals without overcomplicating scoring.

## RRF mental model

Each source gives a ranked list.
RRF adds a small score for each rank position.
If the same note appears in multiple lists, its score rises.
That makes strong cross-signal candidates bubble up naturally.

## Rewrite mental model

Rewrite is a helper, not the main retrieval strategy.
It is used only when the query looks reliable enough.
If the rewrite looks risky, the system falls back to the original query path.

## Reranker mental model

The reranker is a second-stage sorter.
It looks at the fused candidate list and reorders it using a stronger relevance signal.
The current implementation is lightweight and local, and it can be replaced later with:

- a cross-encoder
- an external API
- a Gemini rerank call

Enable the current reranker with `QUERY_RETRIEVAL_RERANKER=token_overlap` (or any truthy value like `true`).

## Implemented chat and memory flow

The chat stack is intentionally simple right now:

- a single-pane frontend chat shell
- persistent chat threads
- stored user and assistant messages
- a backend chat API surface
- thread history returned to the UI

### Chat turn lifecycle

1. User submits a message in the chat UI.
2. Backend creates or loads the thread.
3. The user message is stored.
4. Short-term conversation context is loaded.
5. Retrieval context is added from memory / notes.
6. The assistant response is generated.
7. The assistant message is stored.
8. The thread summary can be refreshed for long conversations.

### Memory layers

NorthStar is moving toward three memory layers:

- **Short-term memory**: recent messages from the active thread
- **Summary memory**: compact thread-level summary for long chats
- **Knowledge memory**: retrieved notes and memories from the existing retrieval pipeline

## Current feature set

- JWT auth
- query quality gate
- LLM rewrite with recent memory context
- rewrite risk detection
- dense retrieval
- BM25 sparse retrieval
- RRF fusion
- optional reranking hook
- chat UI shell
- persistent chat threads
- stored user/assistant messages
- chat API surface that returns thread history
- intent/planner scaffolding for the next agentic phase

## Design notes

- Keep the dense retriever unchanged.
- Keep the code modular and small.
- Prefer simple defaults.
- Postpone directory restructuring until the retrieval flow settles.
- Keep the learning doc updated as each phase lands, but do not mark the learning todo complete yet.

## Agentic workflow mental model

The planned flow is:

User message -> intent detection -> planner -> retrieval/tools -> merge results -> conversation memory -> LLM -> answer -> memory extractor

The key idea is that the planner chooses _what to do_ before the LLM answers:

- retrieval for knowledge lookup
- tool calls for side effects or external data
- direct response when no extra action is needed

This keeps the system easier to reason about than a single monolithic prompt.
