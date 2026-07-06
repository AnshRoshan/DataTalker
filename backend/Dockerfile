# Runs the live DataTalker API (main:fastapi_app).
# Single worker keeps the in-process schema cache coherent; a shared cache + multiple
# workers is a later phase (see docs/CODEBASE_AUDIT.md PR-04).
FROM python:3.13-slim

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

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request as u,sys; sys.exit(0 if u.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["uv", "run", "--no-sync", "uvicorn", "main:fastapi_app", "--host", "0.0.0.0", "--port", "8000"]
