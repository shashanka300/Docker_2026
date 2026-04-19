# Docker AI Demo

A fully local RAG Q&A stack — ask questions about any document using a local LLM. No cloud, no API keys, no data leaving your machine.

Demonstrates every concept from [Docker for AI Builders](docs/docker-ai-guide.md):
multi-stage Dockerfile, non-root user, health checks, Docker Compose, pgvector RAG,
Docker Model Runner, and a containerised MCP server.

```
┌─────────────────────────────────────────────────────┐
│  Browser  →  FastAPI app  →  pgvector (Postgres)    │
│                    ↓                                │
│           Docker Model Runner                       │
│           (llama3.2 + mxbai-embed-large)            │
│                                                     │
│           mcp/postgres  ← AI agent tool access      │
└─────────────────────────────────────────────────────┘
```

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) ≥ 4.40 with **Model Runner** enabled
  *(Settings → Features in development → Enable Docker Model Runner)*

Pull the models once (stored locally, reused across runs):

```bash
docker model pull ai/llama3.2
docker model pull ai/mxbai-embed-large
```

## Run

```bash
docker compose up --build
```

Open **http://localhost:8000** in your browser.

1. Click **Load Sample Doc** — ingests `docs/docker-ai-guide.md` into pgvector
2. Type a question in the Query panel, e.g.:
   - *What are the 4 Dockerfile rules?*
   - *How does multi-stage build reduce image size?*
   - *What is the difference between ivfflat and hnsw?*

## Local development (without Docker)

```bash
uv sync
# needs a local Postgres with pgvector and a running Model Runner
DATABASE_URL=postgresql://user:pass@localhost:5432/mydb uv run uvicorn app.main:app --reload
```

Run tests (no external services needed):

```bash
uv run pytest -v
```

## Project layout

```
app/
  main.py          FastAPI app — endpoints, lifespan, static serving
  db.py            psycopg3 connection + schema init
  rag.py           chunk → embed → store / retrieve → answer
  static/
    index.html     Single-page UI (vanilla JS, no build step)
docs/
  docker-ai-guide.md  Sample document — ingest this to try the demo
tests/
  test_rag.py      Unit tests (chunking + mocked FastAPI endpoints)
init.sql           pgvector schema — mounted into Postgres on first start
Dockerfile         Multi-stage, non-root, pinned UV, health check
compose.yml        app + db (pgvector) + mcp-postgres
```

## Dockerfile concepts illustrated

| Blog rule | Where |
|-----------|-------|
| Layer order — deps before source | `COPY pyproject.toml` then `COPY app/` |
| Non-root user | `adduser appuser` + `USER appuser` |
| Health check tests real deps | `/health` calls `SELECT 1` on Postgres |
| Multi-stage build | `builder` stage → `python:3.11-slim` runtime |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://user:pass@localhost:5432/mydb` | Postgres connection |
| `LLM_BASE_URL` | `http://localhost:12434/engines/llama.cpp/v1` | Model Runner URL |
| `LLM_MODEL` | `ai/llama3.2` | Chat model |
| `EMBED_MODEL` | `ai/mxbai-embed-large` | Embedding model |
| `CHUNK_SIZE` | `400` | Words per chunk |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks |
