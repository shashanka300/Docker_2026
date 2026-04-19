# ── Stage 1: install dependencies ────────────────────────────────────────────
# Use a pinned UV version so the build is reproducible (Rule 4 from the guide)
FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.4.15 /uv /usr/local/bin/uv

WORKDIR /app

# UV flags: compile .pyc at install time, use copy mode (required in Docker)
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Copy only the dependency manifest first (Rule 1 — deps before source code)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project


# ── Stage 2: lean runtime image ───────────────────────────────────────────────
FROM python:3.11-slim

# Copy the pre-built virtualenv from the builder — no pip/uv needed at runtime
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Source and assets in a single layer — changes here don't bust the dep cache
COPY app/ app/
COPY docs/ docs/

# Rule 2 — never run as root
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser /app
USER appuser

# Rule 3 — health check tests a real dependency (the DB via /health)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
