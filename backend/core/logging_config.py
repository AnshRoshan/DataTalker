# core/logging_config.py
"""Structured logging + a per-request correlation ID.

ponytail: this is the observability backbone (PR-06). The ~100 legacy print() calls in
the agents still go to stdout; sweeping them to logger.debug (and out of production log
levels) is a follow-up — they're noisy but no longer the only signal now that every
request is logged with a correlation id.
"""
import logging
import os
import sys
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

logger = logging.getLogger("datatalker")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging() -> None:
    """Configure root logging once. Level from LOG_LEVEL (default INFO)."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s")
    )
    handler.addFilter(_RequestIdFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a correlation id per request and log a one-line summary.

    Logs only method/path/status/latency — never bodies — so SQL/schema/PII don't leak
    into logs. The id is returned as X-Request-ID so a client error can be traced back.
    """

    async def dispatch(self, request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        token = request_id_var.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            # log inside the try so the request_id contextvar is still set
            logger.info(
                "%s %s -> %s (%.0fms)",
                request.method,
                request.url.path,
                response.status_code,
                (time.perf_counter() - start) * 1000,
            )
            response.headers["X-Request-ID"] = rid
            return response
        except Exception:
            logger.exception("%s %s -> unhandled error", request.method, request.url.path)
            raise
        finally:
            request_id_var.reset(token)
