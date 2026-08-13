Prompts for note processing (phase3-v1)

This folder contains the LLM prompt templates used by the backend note processing pipeline.

Versioning
- Each version should be placed in its own subfolder (e.g. `phase3-v1`, `phase3-v2`).
- When updating prompts, create a new folder for the new version and update the environment variable `WORK_MEMORY_PROMPT_VERSION` accordingly.

Files
- `00-gemini_extraction_prompt.txt` — extraction prompt template used by `gemini_client.generate_gemini_prompt`.
- `01-query_rewrite_prompt.txt` — query rewrite prompt used by `query_rewriter.generate_rewrite_prompt`.
- `02-chat_prompt.txt` — chat prompt used by `chat.orchestrator._build_chat_prompt`.

Usage
- These files are purely a source-of-truth for prompt text. To load them at runtime, read the appropriate file from `backend/app/prompts/{version}/` and format with the runtime values.
