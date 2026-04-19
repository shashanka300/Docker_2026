# Docker AI Demo

A fully local RAG Q&A stack — ask questions about any document using a local LLM. No cloud, no API keys, no data leaving your machine.

Demonstrates every concept from [Docker for AI Builders](docs/docker-ai-guide.md):
multi-stage Dockerfile, non-root user, health checks, Docker Compose, pgvector RAG,
Ollama LLM serving, and a containerised MCP server.

```
┌─────────────────────────────────────────────────────┐
│  Browser  →  FastAPI app  →  pgvector (Postgres)    │
│                    ↓                                │
│              Ollama container                       │
│           (llama3.2 + mxbai-embed-large)            │
│                                                     │
│           mcp/postgres  ← AI agent tool access      │
└─────────────────────────────────────────────────────┘
```

## Prerequisites

Docker — either [Docker Desktop](https://www.docker.com/products/docker-desktop/) or **Colima** (macOS/Linux):

```bash
brew install colima docker docker-compose
colima start
```

## Quick start

```bash
# 1. Start the stack (first run pulls ~4 GB of model data)
docker-compose up --build -d

# 2. Pull the LLM models into Ollama (one-time, models are cached in a volume)
docker-compose exec ollama ollama pull llama3.2
docker-compose exec ollama ollama pull mxbai-embed-large

# 3. Open the UI
open http://localhost:8000
```

Then in the browser:
1. Click **Load Sample Doc** — ingests `docs/docker-ai-guide.md` into pgvector
2. Ask questions in the Query panel, e.g.:
   - *What are the 4 Dockerfile rules?*
   - *How does multi-stage build reduce image size?*
   - *What is the difference between ivfflat and hnsw?*

## Development workflow

Edit code, then rebuild only the app container — db and Ollama keep running:

```bash
docker-compose up --build -d app    # rebuilds app only, db + ollama untouched
docker-compose logs -f app          # tail live logs
```

Unit tests mock all external deps, so run them locally with uv:

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
compose.yml        app + db (pgvector) + ollama + mcp-postgres
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
| `LLM_BASE_URL` | `http://localhost:11434/v1` | Ollama API URL |
| `LLM_MODEL` | `llama3.2` | Chat model |
| `EMBED_MODEL` | `mxbai-embed-large` | Embedding model |
| `CHUNK_SIZE` | `200` | Words per chunk |
| `CHUNK_OVERLAP` | `20` | Overlap between chunks |

## Useful commands

```bash
docker-compose logs -f app               # app logs
docker-compose logs -f ollama            # model server logs
docker-compose down -v                   # stop and wipe volumes
docker-compose exec ollama ollama list   # see pulled models
```
