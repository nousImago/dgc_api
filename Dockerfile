# ---- DGC API ----
# Multi-stage: install deps with uv, run with plain Python.
#
# Build:
#   docker build -t dgc-api .
#
# Run:
#   docker run -p 8000:8000 --env-file .env dgc-api

FROM python:3.12-slim AS builder

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first (layer cache)
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

# Copy application code
COPY . .

# ---- Runtime ----
FROM python:3.12-slim

WORKDIR /app

# WeasyPrint runtime deps: Pango handles text shaping (incl. Thai),
# Cairo / GLib / Fontconfig come in transitively via libpango.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
# Copy application source
COPY --from=builder /app /app

# Put the venv on PATH
ENV PATH="/app/.venv/bin:$PATH"
# Force unbuffered output (important for K8s log collection)
ENV PYTHONUNBUFFERED=1
# JSON logs by default in containers (override with LOG_FORMAT=console)
ENV LOG_FORMAT=json

EXPOSE 8000

# Uvicorn with 2 workers (tune via UVICORN_WORKERS env var)
CMD ["python", "-m", "uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
