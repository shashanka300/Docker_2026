# Docker for AI Builders: From Local LLM Serving to Agentic Stacks

Everything you need to know about containerising your AI stack - without the fluff.

## Why Docker at All?

Imagine three engineers on a team. One on Mac, one on Windows, one on Linux. Each has a slightly different Python version and different CUDA drivers. The LLM app works fine locally, fails for two of them, and halves throughput in production.

Docker solves this by packaging your application — code, runtime, libraries, system dependencies — into a self-contained unit called a container. Every machine runs it identically.

Containers vs VMs: A VM carries a full operating system per app — gigabytes, minutes to boot. A container shares the host OS kernel. Your 1.2 GB Python ML service becomes ~180 MB. Boot time drops to seconds.

## Three Concepts to Internalise

**Image** — A read-only snapshot of your app and everything it needs to run. Build once, run anywhere. Nothing a running container does can modify the image underneath.

**Container** — A running instance of an image. Docker adds a thin writable layer on top for logs and temp data. When the container stops, that layer is discarded. Images are immutable; containers are ephemeral.

**Registry** — A remote store for images. Docker Hub is the public default. When you run `docker run python:3.12-slim`, Docker checks locally, doesn't find it, and automatically pulls it.

## The Four Dockerfile Rules That Actually Matter

### Rule 1 — Layer order is a performance decision

Every instruction creates a layer. Docker caches layers. The moment a layer changes, Docker invalidates everything below it and reruns those steps.

BAD: pip install reruns on every code change because source is copied first.
GOOD: copy requirements.txt, install deps (cached), then copy source code last.

The rule: things that change least go near the top. Your dependency manifest rarely changes. Your source code changes constantly. Keep them in separate layers.

### Rule 2 — Never run as root

Without an explicit user, your app runs as root inside the container. Root inside a container can escalate to the host if there is a kernel vulnerability or misconfiguration. Two lines fix this:

```
RUN adduser --disabled-password --gecos "" appuser
USER appuser
```

Everything from the USER instruction onwards runs with minimum privileges.

### Rule 3 — Health checks that test something real

A container showing Up in docker ps says nothing about whether your app is actually working. Your LLM service could have lost its database connection, crashed silently, or be returning 500 on every request.

```
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
```

In FastAPI, test real dependencies, not just process liveness:

```python
@app.get("/health")
async def health():
    await db.execute("SELECT 1")   # verify database is reachable
    return {"status": "ok"}
```

### Rule 4 — Pin base images by digest

Tags are mutable. The maintainer can push a new image to python:3.12-slim tomorrow and your next build silently pulls something different. A digest is a SHA256 fingerprint — it never changes.

```
FROM python:3.12-slim@sha256:a1b2c3d4e5f6...
```

Get the digest with: `docker inspect --format='{{index .RepoDigests 0}}' python:3.12-slim`

## Multi-Stage Builds

When you install packages with pip, you also download build tools and compilers — needed to build, not to run. Multi-stage builds let you compile in one stage and copy only the output into a clean runtime image. A typical Python ML service shrinks from ~1.2 GB to ~180 MB.

```
Stage 1 (builder): pip install --prefix=/install -r requirements.txt
Stage 2 (runtime): COPY --from=builder /install /usr/local
```

## Docker Compose — Running a Full Stack

A single docker run runs one container. Real AI applications have an app server, a database, an embedding store, and often a model server. Docker Compose defines your entire stack in one file and starts everything with one command.

Services in the same Compose file reach each other by service name — your app connects to db:5432, not localhost:5432. Docker creates a private network automatically.

Use `depends_on` with `condition: service_healthy` so services wait for dependencies to be ready before starting.

## Docker Model Runner

Docker Model Runner lets you pull open-weight models from Docker Hub and run them locally. The API it exposes is intentionally identical to the OpenAI API — any code written against OpenAI works with a local model with one line changed. Your data never leaves your machine and you pay no per-token cost.

```
docker model pull ai/llama3.2
docker model pull ai/mxbai-embed-large   # embedding model for RAG
docker model run ai/llama3.2
```

Then call it from Python using the OpenAI SDK — no code changes needed, just change base_url to:
`http://localhost:12434/engines/llama.cpp/v1`

Switch back to OpenAI at any point by restoring the original base_url. Streaming and embeddings work identically.

### Available Models

- **ai/llama3.2** — General chat and instruction following
- **ai/mistral** — Fast, efficient general purpose
- **ai/phi3.5** — Lightweight, runs well on CPU
- **ai/mxbai-embed-large** — Embeddings for RAG (1024 dimensions)
- **ai/nomic-embed-text** — Smaller, faster embeddings

## RAG with pgvector — Fully Local

RAG (Retrieval-Augmented Generation) stores your documents as embedding vectors in a database. At query time it finds the most relevant documents and passes them as context to the model. This lets the model answer questions about your own data — no fine-tuning, no API calls to external services.

The `pgvector/pgvector:pg16` Docker image ships Postgres with the vector extension pre-installed.

The `<=>` operator is pgvector's cosine distance. Nearest neighbours are the most semantically relevant documents.

The vector dimension must match your embedding model. For `ai/mxbai-embed-large`, use `vector(1024)`.

For indexing, use `hnsw` (works without pre-existing rows) or `ivfflat` (faster for large datasets but requires training data).

## GPU Access for Faster Inference

By default Docker containers cannot see the host GPU. Two steps to fix this:

1. Install NVIDIA Container Toolkit on the host and configure the Docker runtime.
2. Expose GPUs in your containers with `--gpus all` or using the `deploy.resources.reservations.devices` block in Compose.

Verify inside a container with: `docker run --gpus all nvidia/cuda:12.0-base nvidia-smi`

For production GPU inference, base your image on `nvidia/cuda:12.1-cudnn8-runtime-ubuntu22.04`.

## MCP Servers as Isolated Containers

Model Context Protocol (MCP) lets AI agents connect to external tools — databases, GitHub, monitoring systems, APIs. Docker Hub now ships verified MCP server images.

Before Docker MCP images, running an MCP server meant installing packages globally on the host with no isolation, no resource limits, no clean way to stop one without affecting others.

Now each MCP server runs in a container with its own network boundary, resource limits, and secrets. To revoke access, stop the container. To add another tool, add another service. No global installs. No credential sprawl.

```yaml
mcp-postgres:
  image: mcp/postgres
  environment:
    - POSTGRES_CONNECTION_STRING=postgresql://user:pass@db:5432/mydb

mcp-github:
  image: mcp/github
  environment:
    - GITHUB_PERSONAL_ACCESS_TOKEN=${GITHUB_TOKEN}
```

Available verified MCP images include GitHub, Grafana, MongoDB, Postgres, and more.

## Production Checklist

**Image hygiene:**
- Base image pinned by digest, not just tag
- Scanned with `docker scout cves` — no unaddressed critical CVEs
- Multi-stage build if your app needs build tools

**Security:**
- Non-root user before CMD
- No secrets baked into image layers
- Minimal base image

**Reliability:**
- HEALTHCHECK tests real dependencies
- `--restart unless-stopped` for production containers
- Named volumes for data that must survive restarts

**Build performance:**
- Dependencies installed before source code
- `.dockerignore` in place
