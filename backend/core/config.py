# core/config.py
"""Configuration settings for the Talk to DB API."""

import os
from dotenv import load_dotenv

load_dotenv()  # so env-driven settings below also honor backend/.env

# Cache settings
CACHE_EXPIRY_SECONDS = 3600  # 1 hour cache expiry

# File upload settings
ALLOWED_EXTENSIONS = [".db", ".sqlite", ".sqlite3"]
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# Database settings
SUPPORTED_DIALECTS = ["sqlite", "postgresql"]

# API settings
API_TITLE = "Talk to DB API"
API_VERSION = "1.0.0"
API_DESCRIPTION = "API for chatting with databases using natural language"

# CORS settings — explicit origins (no wildcard-with-credentials). Override via env
# CORS_ALLOWED_ORIGINS as a comma-separated list.
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]
CORS_ALLOW_CREDENTIALS = False
CORS_ALLOW_METHODS = ["*"]
CORS_ALLOW_HEADERS = ["*"]

# Request timeout settings
REQUEST_TIMEOUT = 30  # seconds

# Temporary file settings
TEMP_FILE_PREFIX = "talkdb_"