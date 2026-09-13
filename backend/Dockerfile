# DataTalker — self-hostable, single-container image.
# Stage 1 builds the React SPA with bun; stage 2 runs the FastAPI API and serves the
# built SPA from the same process (see main.py _mount_spa). Build context = repo root:
#   docker build -f backend/Dockerfile -t datatalker .
# Single worker keeps the in-process schema cache coherent (see audit PR-04).

# ---- Stage 1: frontend -------------------------------------------------------
FROM oven/bun:1 AS web
WORKDIR /web
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile
COPY frontend/ .
RUN bun run build

# ---- Stage 2: API + SPA ------------------------------------------------------
FROM python:3.13-slim

LABEL org.opencontainers.image.title="DataTalker" \
      org.opencontainers.image.description="Chat with your database in natural language — NL to SQL with a read-only safety pipeline" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv && useradd --create-home app

# Install backend dependencies from the lockfile (uv.lock is the source of truth).
COPY backend/pyproject.toml backend/uv.lock /app/backend/
WORKDIR /app/backend
RUN uv sync --frozen --no-install-project --no-dev

# App source + built SPA
COPY backend/ /app/backend/
COPY --from=web /web/dist /app/frontend/dist
RUN chown -R app:app /app
USER app

# Persisted state: connections registry + audit log live here; mount volumes to keep
# them across container upgrades.
VOLUME ["/app/backend/data", "/app/backend/logs"]

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request as u,sys; sys.exit(0 if u.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["uv", "run", "--no-sync", "uvicorn", "main:fastapi_app", "--host", "0.0.0.0", "--port", "8000"]
