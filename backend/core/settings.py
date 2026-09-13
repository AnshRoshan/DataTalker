# core/settings.py
"""Single source of configuration (EC-07/PR-07): pydantic-settings loaded from
process env + backend/.env.

All fields default to the previous hardcoded values from core/config.py, so
behavior is unchanged when nothing is set. Env vars use the DATATALKER_ prefix
(e.g. DATATALKER_MAX_QUERY_ROWS); CORS_ALLOWED_ORIGINS is also honored under
its old name for backwards compatibility.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ directory — the default confinement dir for db_path and the base for
# relative paths (audit log, etc.).
_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="DATATALKER_", extra="ignore"
    )

    # API
    api_title: str = "Talk to DB API"
    api_version: str = "1.0.0"
    api_description: str = "API for chatting with databases using natural language"

    # CORS — explicit origins (no wildcard-with-credentials). Comma-separated.
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias=AliasChoices("DATATALKER_CORS_ORIGINS", "CORS_ALLOWED_ORIGINS"),
    )
    cors_allow_credentials: bool = False
    cors_allow_methods: str = "*"
    cors_allow_headers: str = "*"

    # Schema cache
    cache_ttl_seconds: int = 3600

    # Uploads
    allowed_upload_extensions: str = ".db,.sqlite,.sqlite3"
    max_upload_mb: int = 100

    # Database confinement (db_path must live inside this directory)
    db_dir: str = str(_BACKEND_DIR)

    # Dialects accepted across the app (EC-03 added mysql)
    supported_dialects: list[str] = ["sqlite", "postgresql", "mysql"]

    # Query guards
    max_query_rows: int = 500          # hard server-side row cap (EC-10)
    statement_timeout_seconds: int = 30

    # Rate limiting (0 disables)
    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60

    # Audit log ("" disables). Relative paths resolve against the backend dir.
    audit_log_path: str = "logs/audit.log"

    # Optional governance JSON / semantic YAML ("" = feature off)
    governance_file: str = ""
    semantic_file: str = ""

    # Temp file naming
    temp_file_prefix: str = "talkdb_"

    # Request timeout for URL downloads (was REQUEST_TIMEOUT in config.py)
    request_timeout_seconds: int = 30

    # --- computed views (kept as properties so env only carries raw strings) ---
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_extensions_list(self) -> list[str]:
        return [e.strip().lower() for e in self.allowed_upload_extensions.split(",") if e.strip()]

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def audit_log_file(self) -> Path:
        """Resolved audit path, or an empty Path when disabled."""
        if not self.audit_log_path:
            return Path()
        p = Path(self.audit_log_path)
        return p if p.is_absolute() else _BACKEND_DIR / p

    @property
    def governance_file_path(self) -> Path:
        if not self.governance_file:
            return Path()
        p = Path(self.governance_file)
        return p if p.is_absolute() else _BACKEND_DIR / p

    @property
    def semantic_file_path(self) -> Path:
        if not self.semantic_file:
            return Path()
        p = Path(self.semantic_file)
        return p if p.is_absolute() else _BACKEND_DIR / p


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide Settings singleton. Call get_settings.cache_clear() in tests."""
    return Settings()
