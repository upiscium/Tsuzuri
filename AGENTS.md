# AGENTS.md

## Commands
- Use `just check-all` for full verification; it runs lint, typecheck, and tests.
- Direct equivalents are `uv run ruff check src tests`, `uv run mypy src`, and `uv run pytest`.
- Run `uv run ruff format src tests` before final verification.

## Setup And Config
- This repo is a `uv` + Nix Python project. `.envrc` uses the flake and synchronizes the uv environment.
- Keep secrets in `.env`; use `.env.example` for expected secret keys.
- Keep non-secret endpoints and tunables in `settings.toml`.
- The LLM boundary is an OpenAI-compatible `/v1/chat/completions` API. Do not add backend-specific Ollama, vLLM, llama.cpp, or SGLang assumptions to pipeline code.
- Legacy `TSUZURI_OLLAMA_*` settings are compatibility aliases only and should not be used in new documentation or code.

## Architecture Notes
- Main flow is `Search -> Candidate ranking/pruning -> Fetch -> Document selection -> Map -> Global Reduce -> Final Markdown -> Upload` in `src/tsuzuri/pipeline.py`.
- SearXNG engine/rank/category/score metadata is retrieval metadata. Do not put it into LLM prompts.
- LLM prompts receive source IDs, titles, extracted content, and validated map summaries; raw URLs stay outside prompts.
- `src/tsuzuri/report.py` owns final Markdown assembly and source URL mapping.
- Structured output is optional at the serving backend. The OpenAI-compatible client must retain JSON Schema -> JSON object -> prompt fallback behavior when configured as `auto`.
- Fetch failures should remain diagnosable through persisted `FailedFetch` metadata. Do not collapse HTTP, content-type, extraction, and WAF failures into one generic error.
- PDF support is part of the main pipeline. Unknown/HTML URLs that return PDF content-type are rerouted to the PDF fetcher.
- Search expansion must avoid unnecessary burst concurrency because upstream SearXNG engines may rate-limit or CAPTCHA.

## Verification
- Network and LLM behavior must be mocked in unit tests.
- Retrieval changes should add deterministic ranking/filtering tests.
- Run full Ruff, mypy, and pytest before publishing a candidate branch.
- When testing against the configured SearXNG instance, treat `200 + empty results + unresponsive_engines` as a transient search outage, not a successful zero-result query.

- Treat `reasoning_effort` as a standardized optional chat-completions request field; do not use native backend-specific `think` parameters. On the 2–12B non-reasoning Map baseline, set it to `none` to avoid exhausting `max_tokens` before JSON content is produced.
