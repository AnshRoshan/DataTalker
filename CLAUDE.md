# CLAUDE.md — DataTalker

> Working guide for AI agents and humans. Verified against the actual code after the
> Phase-3 wave (2026-09-13, branch `phase3-next-level`). Full findings + roadmap:
> [`docs/CODEBASE_AUDIT.md`](docs/CODEBASE_AUDIT.md) (see the Phase-3 status banner there).

## What this is

DataTalker is a "talk to your data" app: ask a natural-language question, it reflects a
database's schema, uses an LLM (Gemini by default; any OpenAI-compatible endpoint via
`LLM_*` config) to write SQL, executes it read-only, and returns a plain-English answer +
the SQL + the result rows. FastAPI backend + React/Vite (TypeScript) frontend.

**Status: Phase-3 hardened + feature-complete for a single-tenant tool.** Security hardening
(Phases 0–1) and the pluggable LLM (Phase 2A) landed earlier; Phase 3 added: env-driven
settings, pooled DB engines, per-IP rate limiting, a hard row cap + statement timeouts, a
real readiness `/health`, a JSONL audit log, governance-lite (table allowlist + column
masking), a semantic-layer YAML glossary, MySQL dialect support, and multi-turn chat
history. All 18 `backend/test_*.py` scripts pass; the full `/chat/` pipeline is verified
end-to-end (mock LLM) against `backend/hospital.db`.

## Repo layout (all of it is real now — the dead "enterprise" stack and legacy UI are gone)

```
backend/
  main.py                 LIVE entry — uvicorn main:fastapi_app on :8000; CORS + rate-limit middleware
  api/
    endpoints.py          /chat/ /schema/ /schema/cache (GET+DELETE) / /  /health
    dependencies.py       resolves db_file / db_path / db_url / db_connection_string; require_api_key
    models.py             Pydantic response models (handlers return JSONResponse; shapes match)
  services/
    schema_service.py     schema extraction + cache orchestration + governance filter
    query_service.py      NL→SQL orchestration; history, governance masking, response shaping
  graphs/
    query_graph.py        LIVE LangGraph: writer→validator→executor→(retry)→formatter
    schema_graph.py       LIVE single-node schema-reflection graph
  agents/                 the 7 pipeline agents
    sql_writer.py  validator.py  db_executor.py  answer.py
    schema.py  user_input.py  fallback.py  sql_retry.py
  llm/                    pluggable LLM layer (EC-01): base.py protocol, providers/ (gemini,
                          openai_compat), factory.py (env-driven), prompts.py (dialect-aware),
                          service.py (the 2 funcs agents call; retry loop lives here)
  core/
    settings.py           pydantic-settings (env + backend/.env, DATATALKER_ prefix) — single config source
    engines.py            pooled SQLAlchemy engines per db_uri (bounded, TTL-evicted); SQLite query_only pin
    ratelimit.py          sliding-window per-IP limiter (middleware on POST /chat/ + /schema/)
    audit.py              append-only JSONL audit log (who-asked-what + SQL verdict + latency)
    governance.py         optional JSON: allowed_tables + masked_columns (full/partial/hash)
    semantic.py           optional YAML glossary (table/column descriptions, synonyms, metrics)
    dialects.py           dialect registry (sqlite/postgresql/mysql → prompt snippets)
    cache.py              the ONE schema cache (service dict + agent LRU share it, TTL'd)
    database.py           connection-string parsing + db_path confinement (SEC-04)
    file_handler.py       upload/download temp-file handling (mkstemp, size caps, SSRF guard)
    logging_config.py     structured logging + per-request X-Request-ID
  Database/PopulateDB.py  Faker-based sample-data generator
  hospital.db, multi_table.db   ready-to-use SQLite fixtures
  governance.example.json  semantic.hospital.yml   ← example configs for the two optional features
  test_*.py               18 assert-based test scripts run directly (`uv run python test_x.py`)

frontend/                 React 19 + Vite 6 + Tailwind 4, package manager = bun
  src/App.tsx             single sendQuestion() flow; history, abort/timeout, persistence
  src/components/         ChatArea, ChatMessage (pagination + CSV in ResultsTable), Sidebar
                          (real file upload), Header (live health badge), Settings, ...
  src/lib/                storage.ts (localStorage), csv.ts (RFC-4180 export)
  src/types.ts            response types (incl. results_truncated / latency_ms / row_cap)
```

## The live API contract (`api/endpoints.py`)

- `POST /chat/` — **multipart form**. Fields: `question` (required), exactly one DB
  reference (`db_file` upload | `db_path` server-absolute path | `db_url` | `db_connection_string`),
  optional `history` (JSON array of last turns `{question, answer, sql}`, max 5 kept).
  Returns `{ answer, sql, results, follow_up_questions, results_truncated, sql_executed,
  validator_rejected, latency_ms }`.
- `POST /schema/` — extract & cache schema only.
- `GET /schema/cache`, `DELETE /schema/cache` — inspect / clear the schema cache.
- `GET /` (info), `GET /health` (real readiness: 200 healthy / 503 degraded if settings or
  the LLM provider can't be built).

DB reference resolution priority (`api/dependencies.py`): `db_connection_string` > `db_path`
> `db_file` > `db_url`.
- `db_path` = an **absolute path on the SERVER's filesystem**, confined to
  `DATATALKER_DB_DIR` (default `backend/`). The frontend's default tab uploads the actual
  file (`db_file`) instead — server paths are an "Advanced" option.
- `db_connection_string` = `sqlite:///abs/path`, `postgresql://user:pass@host/db`, or
  `mysql://user:pass@host/db` (pymysql).
- `results` is a flat `list[dict]` (single read-only SELECT is enforced; multi-statement
  rejected by the validator AND the executor).

## Running it locally

**Backend** (needs `GEMINI_API_KEY` — or `LLM_PROVIDER=openai` + `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL`
— **and `DATATALKER_API_KEY`** in `backend/.env`; missing LLM config surfaces as a clear error on the
first LLM call, and every data request is denied without the API key):
```bash
cd backend
# backend/.env (gitignored):
#   GEMINI_API_KEY=...
#   DATATALKER_API_KEY=<a long random secret>   # clients send: Authorization: Bearer <it>
uv run uvicorn main:fastapi_app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
bun install
bun run dev          # Vite dev server, defaults to http://localhost:5173
```
The frontend calls the backend at `localStorage.apiUrl` or `http://127.0.0.1:8000` by default
(configurable in the Settings panel).

**Smoke-test the LIVE path** (no browser needed) — use a bundled fixture with an **absolute**
path (both separators work):
```bash
curl -X POST http://127.0.0.1:8000/chat/ \
  -H "Authorization: Bearer $DATATALKER_API_KEY" \
  -F "question=How many patients are there?" \
  -F "db_path=E:/GENAI-PROJECTS/DataTalker/backend/hospital.db"
```
Without a valid LLM key you can still E2E-test by pointing `LLM_PROVIDER=openai` +
`LLM_BASE_URL` at any OpenAI-compatible mock (the provider seam makes this trivial).

## The NL→SQL pipeline

`query_graph.py` wires: **SQLWriterAgent** (LLM writes SQL or decides no SQL is needed; gets
dialect snippet + governance note + semantic glossary + chat history as extra context) →
**ValidatorAgent** (single read-only `SELECT`/`WITH`; rejects masked columns) →
**DBExecutorAgent** (pooled engine, hard row cap, statement timeout on server DBs, SQLite
`query_only` pin) → optional **SQLRetryAgent** (max 2 retries when results are empty) →
**AnswerFormatterAgent** (LLM turns rows into a NL answer + follow-up questions). Schema is
reflected once by **SchemaAgent** and cached in the single TTL'd cache. Optional governance
masking is applied to result rows before they leave `query_service`.

## Configuration (all env-driven via `core/settings.py`, prefix `DATATALKER_`)

`DATATALKER_API_TITLE/VERSION, DATATALKER_CORS_ORIGINS` (alias `CORS_ALLOWED_ORIGINS`),
`DATATALKER_CACHE_TTL_SECONDS=3600, DATATALKER_ALLOWED_UPLOAD_EXTENSIONS=.db,.sqlite,.sqlite3,
DATATALKER_MAX_UPLOAD_MB=100, DATATALKER_DB_DIR, DATATALKER_MAX_QUERY_ROWS=500,
DATATALKER_STATEMENT_TIMEOUT_SECONDS=30, DATATALKER_RATE_LIMIT_REQUESTS=30 (0=off),
DATATALKER_RATE_LIMIT_WINDOW_SECONDS=60, DATATALKER_AUDIT_LOG_PATH=logs/audit.log (""=off),
DATATALKER_GOVERNANCE_FILE="" , DATATALKER_SEMANTIC_FILE=""`. LLM config (no prefix):
`LLM_PROVIDER=gemini|openai`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`.

## Definition of done for changes here

- Verify against the **live** path (`main:fastapi_app` + a fixture DB), not just unit tests.
- Prefer **deletion/consolidation** over adding another way to do something.
- Don't reintroduce doc/reality drift: if you change behavior, update this file and the audit.
- Test changes as assert-based scripts in `backend/test_*.py` (run directly with
  `uv run python test_x.py`; there is no pytest).
