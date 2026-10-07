# Tsuzuri

Local LLM news research pipeline.

Tsuzuri is an MVP Python implementation of a local-LLM-powered news research
pipeline. It searches, fetches, summarizes, renders a cited Markdown report, and
optionally uploads artifacts to Nextcloud WebDAV.

The current implementation contains a runnable local pipeline. It searches
through SearXNG, aggregates and prunes candidates, fetches HTML and PDF sources,
summarizes through an OpenAI-compatible API, synthesizes a cited global brief,
and optionally uploads artifacts to WebDAV.

## MVP Status

This project is ready for local, personal, and demo use through the CLI, HTTP
API, Docker Compose, and React web UI. It is not yet hardened for public
multi-user production deployment.

Production gaps to address before public exposure:

- No authentication or authorization on the API/UI.
- Run state is in memory while the API process is alive.
- Run history is not reconstructed from existing `outputs/` artifacts yet.
- Cluster-level reduce is not implemented; global reduce currently runs directly over selected map summaries.
- Discord notification is not implemented.

## Current Status

Implemented:

- Pydantic schemas for pipeline data.
- URL normalization, deduplication, domain filtering, and document-type routing.
- Topic-neutral rule-based query expansion.
- Async SearXNG JSON API client with retry for transient engine outages.
- Cross-query candidate aggregation and deterministic ranking/pruning.
- HTML fetch validation and extraction with `httpx` and `trafilatura`.
- PDF fetching with PyMuPDF, wired into the main pipeline.
- Fetch diagnostics including final URL, HTTP status, content type, response size,
  raw text size, and extraction failure reason.
- Local artifact storage under `outputs/{run_id}/`.
- Pipeline orchestration for search, ranking, concurrent fetch, map summarization,
  global reduce, report rendering, and artifact saving.
- OpenAI-compatible `/v1/chat/completions` client with optional JSON Schema /
  JSON-object structured output and prompt fallback.
- Optional WebDAV artifact upload with warn-and-continue failure behavior.
- Citation extraction, validation, and final Markdown source rendering.
- FastAPI HTTP API for external applications.
- React dark themed web UI with progress polling and final report preview.
- Docker and Docker Compose support.
- Unit tests for the implemented modules.

Not implemented yet:

- Authentication / access control.
- Persistent run history across API restarts.
- Discord notification.
- Cluster-level reduce and embedding-based clustering.
- Browser/Playwright fetch fallback in the default runtime (the HTML fetcher keeps
  the fallback hook, but no browser implementation is wired yet).
- Retrieval quality benchmark fixtures and metrics.

## Requirements

- Python 3.11 or newer.
- `uv`.
- Optional: Nix with direnv support for the repository flake workflow.

## Setup

Synchronize dependencies:

```bash
just sync
```

Or directly:

```bash
uv sync
```

Copy `.env.example` to `.env` when enabling external services later:

```bash
cp .env.example .env
```

Do not commit real secrets.

## Local Run

Run the default local pipeline:

```bash
just deploy
```

Run with a custom query:

```bash
just deploy "AI regulation latest developments"
```

Or call the CLI directly:

```bash
PYTHONPATH=src uv run python -m tsuzuri.cli run "AI regulation latest developments"
```

Artifacts are saved under `outputs/{run_id}/`. WebDAV upload is attempted when
`webdav_base_url`, `NEXTCLOUD_USERNAME`, and `NEXTCLOUD_PASSWORD` are available.
Upload failures are reported as warnings and do not fail the run.

## HTTP API

Start the API server:

```bash
just api
```

Health check:

```bash
curl http://127.0.0.1:8000/healthz
```

Run the pipeline from an external app:

```bash
curl -X POST http://127.0.0.1:8000/runs \
  -H 'Content-Type: application/json' \
  -d '{"query":"AI regulation latest developments"}'
```

The response includes run counts, warnings, and the local path to
`final_report.md`.

The API starts runs in the background. Poll `GET /runs/{run_id}` for progress,
then fetch `GET /runs/{run_id}/final-report` after completion.

The React web UI is served from the API after building frontend assets:

```bash
just frontend-build
just api
```

Open `http://127.0.0.1:8000/ui/` for the dark themed run dashboard with progress
polling and final report preview.

For frontend-only development:

```bash
just frontend-dev
```

## Docker

Build the local image:

```bash
just docker-build
```

Run the API with Docker Compose:

```bash
just docker-up
```

Stop it:

```bash
just docker-down
```

The compose service exposes the API on `http://127.0.0.1:8000`, mounts
`./outputs` for artifacts, and reads `.env` for runtime configuration and
secrets when present.

The Docker image builds the React frontend and serves it from `/ui/` in the same
FastAPI container.

### Use From Another Directory

You can run Tsuzuri from outside this repository with only a Compose file,
`.env`, and an `outputs/` directory.

Copy `example.compose.yml` to your deployment directory as `compose.yml`:

```bash
mkdir -p tsuzuri-deploy/outputs
cd tsuzuri-deploy
curl -fsSLo compose.yml \
  https://raw.githubusercontent.com/uPiscium/Tsuzuri/v0.1.1/example.compose.yml
```

Create `.env`:

```env
TSUZURI_SEARXNG_BASE_URL=https://your-searxng.example.com
TSUZURI_LLM_BASE_URL=http://your-openai-compatible-server.example.com/v1
TSUZURI_LLM_MODEL=qwen3.5:9b
TSUZURI_LLM_API_KEY=
TSUZURI_LLM_STRUCTURED_OUTPUT=auto
TSUZURI_LLM_MAX_TOKENS=2048
TSUZURI_WEBDAV_BASE_URL=https://your-nextcloud.example.com/remote.php/dav/files/your-user/NAS/Tsuzuri

TSUZURI_QUERY_TIMEOUT_S=10.0
TSUZURI_FETCH_TIMEOUT_S=30.0
TSUZURI_LLM_TIMEOUT_S=120.0
TSUZURI_UPLOAD_TIMEOUT_S=15.0
TSUZURI_MAX_CONCURRENT_FETCHES=6
TSUZURI_MIN_SUCCESS_CHARS=500
TSUZURI_PDF_MAX_FILE_MB=30
TSUZURI_PDF_MAX_PAGES=80
TSUZURI_MAX_FETCH_DOCUMENTS=40
TSUZURI_MAX_MAP_DOCUMENTS=12
TSUZURI_MAX_MAP_DOCUMENTS_PER_DOMAIN=2
TSUZURI_SEARCH_LANGUAGE=en
TSUZURI_SEARCH_CATEGORIES=news,general
TSUZURI_ALLOWED_LANGUAGES=en,ja
TSUZURI_USER_AGENT=Tsuzuri/0.2

NEXTCLOUD_USERNAME=your-nextcloud-user
NEXTCLOUD_PASSWORD=your-nextcloud-app-password
DISCORD_WEBHOOK_URL=
```

Start the service:

```bash
docker compose up --build
```

Open the web UI:

```text
http://127.0.0.1:8000/ui/
```

## Development

Run all checks:

```bash
just check-all
```

Focused commands:

```bash
just lint src/
just typecheck src/
just test tests/
```

Format source and tests:

```bash
just format src/
uv run ruff format tests/
uv run ruff check --fix tests/
```

## Configuration

Non-secret defaults live in `settings.toml` for local runs. Docker deployments can
use `TSUZURI_*` environment variables instead of mounting `settings.toml`.

Secret values are expected through environment variables, with placeholders in
`.env.example`:

- `TSUZURI_SEARXNG_BASE_URL`
- `TSUZURI_LLM_BASE_URL`
- `TSUZURI_LLM_MODEL`
- `TSUZURI_LLM_API_KEY`
- `TSUZURI_WEBDAV_BASE_URL`
- `NEXTCLOUD_USERNAME`
- `NEXTCLOUD_PASSWORD`
- `DISCORD_WEBHOOK_URL`

## Roadmap

Next implementation slices:

1. Add retrieval evaluation fixtures and quality metrics (Precision@k, nDCG,
   source quality, freshness, diversity, and fetch success rate).
2. Replace the remaining heuristic query expansion with evaluated query planning.
3. Add cluster-level reduce / event grouping before global synthesis.
4. Add a qualified browser fallback for fetch failures that need JavaScript.
5. Expand supported source/media types after HTML/PDF quality is stable.
6. Add persistent run history and API/UI authentication before public deployment.
