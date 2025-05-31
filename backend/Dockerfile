# TalkToData Enterprise - Multi-stage Docker build
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd --create-home --shell /bin/bash app

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Development stage
FROM base as development

# Install development dependencies
RUN pip install pytest pytest-asyncio httpx black isort flake8

# Copy source code
COPY --chown=app:app . .

# Switch to app user
USER app

# Expose port
EXPOSE 8000

# Development command
CMD ["uvicorn", "enterprise_app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production stage
FROM base as production

# Copy source code
COPY --chown=app:app . .

# Remove development files
RUN rm -rf tests/ .pytest_cache/ .git/

# Switch to app user
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production command
CMD ["uvicorn", "enterprise_app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# Worker stage for Celery
FROM base as worker

# Copy source code
COPY --chown=app:app . .

# Switch to app user
USER app

# Celery worker command
CMD ["celery", "-A", "core.tasks.celery_app", "worker", "--loglevel=info", "--concurrency=2"]

# Celery beat scheduler
FROM base as scheduler

# Copy source code
COPY --chown=app:app . .

# Switch to app user
USER app

# Celery beat command
CMD ["celery", "-A", "core.tasks.celery_app", "beat", "--loglevel=info"]

# Flower monitoring
FROM base as flower

# Install flower
RUN pip install flower

# Copy source code
COPY --chown=app:app . .

# Switch to app user
USER app

# Expose flower port
EXPOSE 5555

# Flower command
CMD ["celery", "-A", "core.tasks.celery_app", "flower", "--host=0.0.0.0", "--port=5555"]
