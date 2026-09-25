# DataTalker — self-hostable, single-container image.
# Stage 1 builds the React SPA with bun; stage 2 runs the FastAPI API and serves the
# built SPA from the same process (see backend/main.py _mount_spa). Build context is the
# repo root, and this file lives there so Git-based builders find it without being told:
#   docker build -t datatalker .
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
    UV_LINK_MODE=copy \
    # Platforms (Rollout, Fly, Render, Heroku-style) assign the port at runtime and
    # probe that number — binding a hardcoded 8000 makes the app look dead. PORT is the
    # override; 8000 keeps plain `docker run` and the compose file working unchanged.
    PORT=8000

RUN pip install --no-cache-dir uv && useradd --create-home app

# Install backend dependencies from the lockfile (uv.lock is the source of truth).
COPY backend/pyproject.toml backend/uv.lock /app/backend/
WORKDIR /app/backend
RUN uv sync --frozen --no-install-project --no-dev

# App source + built SPA
COPY backend/ /app/backend/
COPY --from=web /web/dist /app/frontend/dist
# data/ and logs/ are gitignored (runtime state), so they do not exist in the build
# context. Without creating them here, a fresh mounted volume is root-owned and the
# unprivileged app user cannot write the connections registry or the audit log.
RUN mkdir -p /app/backend/data /app/backend/logs && chown -R app:app /app
USER app

# Persisted state: connections registry + audit log live here; mount volumes to keep
# them across container upgrades.
VOLUME ["/app/backend/data", "/app/backend/logs"]

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import os,urllib.request as u,sys; url='http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'); sys.exit(0 if u.urlopen(url, timeout=5).status==200 else 1)"

# Shell form so ${PORT} expands: a platform that injects PORT gets listened on,
# otherwise the 8000 default above applies.
CMD uv run --no-sync uvicorn main:fastapi_app --host 0.0.0.0 --port ${PORT}
