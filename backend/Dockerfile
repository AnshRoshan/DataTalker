# DataTalker — self-hostable, single-container image for the live API.
# Single worker keeps the in-process schema cache coherent; a shared cache + multiple
# workers is a later phase (see docs/CODEBASE_AUDIT.md PR-04).
FROM python:3.13-slim

LABEL org.opencontainers.image.title="DataTalker" \
      org.opencontainers.image.description="Chat with your database in natural language — NL to SQL with a read-only safety pipeline" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/your-org/DataTalker"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv && useradd --create-home app
WORKDIR /app

# Install dependencies from the lockfile (uv.lock is the source of truth).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# App source
COPY . .
RUN chown -R app:app /app
USER app

# Persisted state: connections registry + audit log live here; mount a volume to keep
# them across container upgrades.
VOLUME ["/app/data", "/app/logs"]

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request as u,sys; sys.exit(0 if u.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["uv", "run", "--no-sync", "uvicorn", "main:fastapi_app", "--host", "0.0.0.0", "--port", "8000"]
