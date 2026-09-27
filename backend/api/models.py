# api/models.py
"""Pydantic models for API requests and responses."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DatabaseInput(BaseModel):
    """Base model for database input methods."""
    db_connection_string: Optional[str] = Field(None, description="Database connection string")
    db_path: Optional[str] = Field(None, description="Local database file path")
    db_url: Optional[str] = Field(None, description="Database URL or download URL")


class SchemaResponse(BaseModel):
    """Response model for schema extraction."""
    message: str
    database_uri: str
    database_dialect: str
    database_path: Optional[str]
    tables: List[str]
    schema_description: str
    cached: bool


class QueryRequest(BaseModel):
    """Request model for chat queries."""
    question: str = Field(..., description="Natural language question")
    database_input: DatabaseInput


class QueryResponse(BaseModel):
    """Response model for chat queries."""
    answer: str
    sql: str
    results: List[Dict[str, Any]]
    follow_up_questions: List[str]
    # Phase-3 additions (response shape only grows; frontend ignores unknown keys)
    results_truncated: Optional[bool] = None
    sql_executed: Optional[bool] = None
    validator_rejected: Optional[bool] = None
    latency_ms: Optional[int] = None
    row_cap: Optional[int] = None


class CacheInfo(BaseModel):
    """Model for cache information."""
    database_hash: str
    database_path: str
    database_uri: str
    cached_at: float
    age_seconds: float
    expires_in_seconds: float
    tables: List[str]


class CacheResponse(BaseModel):
    """Response model for cache information."""
    cached_schemas: List[CacheInfo]
    cache_expiry_seconds: int
    total_cached: int
    agent_cache_entries: Optional[int] = None  # SchemaAgent in-memory layer (ARCH-08)


class ClearCacheResponse(BaseModel):
    """Response model for cache clearing."""
    message: str
    cleared_count: int


class ConversationIn(BaseModel):
    """Body for POST /conversations/ — an upsert of one thread.

    `messages` is client-shaped (the chat payload); the store clips, trims and rebuilds
    it, so nothing here is trusted to be well-formed or small.
    """
    id: Optional[str] = None
    source: Optional[str] = None
    # Deliberately List[Any]: the store sanitizes each entry (drops non-objects, clips
    # long text, trims rows). Typing this as List[Dict] would make a single malformed
    # turn reject the whole thread with a 422 the client cannot act on.
    messages: List[Any] = Field(default_factory=list)


class SavedQueryIn(BaseModel):
    """Body for POST /queries/ — save or update a statement. Never a credential."""
    id: Optional[str] = None
    name: str = ""
    sql: str = Field(..., description="A single read-only statement")
    dialect: Optional[str] = None
    source: Optional[str] = Field(None, description="Display name of the database it targets")


class GoogleCallback(BaseModel):
    """Request body for POST /auth/google — the credential GSI handed the browser."""
    credential: str = Field(..., description="Google ID token, verified server-side")


class AuthUser(BaseModel):
    """Response model for a successful sign-in."""
    email: str
    name: str
    picture: str = ""


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    message: str
    version: Optional[str] = None
    llm_mode: Optional[str] = None  # operator-or-byok | byok-only
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    auth: Optional[str] = None  # required | disabled


class LLMModelEntry(BaseModel):
    """One selectable model from the provider's catalog."""
    id: str
    label: Optional[str] = None


class LLMModelsResponse(BaseModel):
    """Response model for GET /llm/models."""
    provider: str
    model: Optional[str] = None
    models: List[LLMModelEntry] = []
    error: Optional[str] = None


class LLMModelSelect(BaseModel):
    """Request body for POST /llm/model."""
    model: str = Field(..., description="Model id from the provider catalog")


class LLMModelSelection(BaseModel):
    """Response model for POST/DELETE /llm/model."""
    provider: str
    model: Optional[str] = None


class ConnectionCreate(BaseModel):
    """Request body for registering a connection (JSON)."""
    name: str = Field(..., description="Human-friendly connection name")
    connection_string: str = Field(..., description="SQLAlchemy connection string")
    notes: Optional[str] = Field(None, description="Free-form notes")


class ConnectionOut(BaseModel):
    """A registered connection — NEVER carries the real connection string."""
    id: str
    name: str
    connection_string_masked: str
    notes: Optional[str] = None
    created_at: Optional[str] = None
    last_checked_at: Optional[str] = None
    last_status: Optional[Dict[str, Any]] = None
    dialect: Optional[str] = None
    table_count: Optional[int] = None


class ConnectionListResponse(BaseModel):
    """Response model for GET /connections/."""
    connections: List[ConnectionOut]
    total: int


class ConnectionCheckResponse(BaseModel):
    """Response model for POST /connections/{id}/check."""
    id: str
    last_checked_at: Optional[str] = None
    last_status: Optional[Dict[str, Any]] = None


class APIInfo(BaseModel):
    """Response model for API information."""
    message: str
    version: str
    features: List[str]
    endpoints: Dict[str, str]