# CLAUDE.md — DataTalker

> Working guide for AI agents and humans. Verified against the actual code after the
> Phase-3 wave (2026-09-13, branch `phase3-next-level`). Full findings + roadmap:
> [`docs/CODEBASE_AUDIT.md`](docs/CODEBASE_AUDIT.md) (see the Phase-3 status banner there).

## What this is

DataTalker is a "talk to your data" app: ask a natural-language question, it reflects a
database's schema, uses an LLM (Gemini by default; any OpenAI-compatible endpoint via
`LLM_*` config) to write SQL, executes it read-only, and returns a plain-English answer +
the SQL + the result rows. FastAPI backend + React/Vite (TypeScript) frontend.

**Status: Phase-4 scale wave.** Security hardening (Phases 0–1) and the pluggable LLM (Phase 2A)
landed earlier; Phase 3 added env-driven settings, pooled DB engines, rate limiting, row cap +
timeouts, real `/health`, audit log, governance-lite, semantic layer, MySQL, chat history.
Phase 4 added: **schema graph + relevance retrieval** (huge schemas are pruned per-question),
a **connections registry** with **preflight checks**, and **universal SQLAlchemy URL support**
(any dialect; extras for mssql/oracle/snowflake). All 23 `backend/test_*.py` scripts pass; the
full pipeline is verified end-to-end against the bundled fixtures.

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
                          openai_compat), factory.py (env + per-request credentials),
                          request_provider.py (bring-your-own X-LLM-* key, presets, middleware),
                          selection.py (model catalog + runtime model pick), prompts.py
                          (dialect-aware), service.py (the 2 funcs agents call; retry loop lives here)
  core/
    settings.py           pydantic-settings (env + backend/.env, DATATALKER_ prefix) — single config source
    engines.py            pooled SQLAlchemy engines per db_uri (bounded, TTL-evicted); SQLite query_only pin
    schema_graph.py       tables/cols nodes + FK edges + inferred joins; compact prompt renderer
    schema_retrieval.py   per-question relevance pruning of huge schemas (top-K + 1-hop neighbors)
    connections.py        JSON-file registry of saved connections (masked URIs only in responses)
    preflight.py          any-URL connection check (dialect, server version, table count, warnings)
    ratelimit.py          sliding-window per-IP limiter (middleware on POST /chat/ + /schema/)
    audit.py              append-only JSONL audit log (who-asked-what + SQL verdict + latency)
    governance.py         optional JSON: allowed_tables + masked_columns (full/partial/hash)
    semantic.py           optional YAML glossary (table/column descriptions, synonyms, metrics)
    dialects.py           dialect registry (sqlite/postgresql/mysql + generic ANSI fallback)
    cache.py              the ONE schema cache (service dict + agent LRU share it, TTL'd)
    database.py           connection-string parsing + db_path confinement (SEC-04)
    file_handler.py       upload/download temp-file handling (mkstemp, size caps, SSRF guard)
    logging_config.py     structured logging + per-request X-Request-ID
  Database/PopulateDB.py  Faker-based sample-data generator
  hospital.db, multi_table.db   ready-to-use SQLite fixtures
  governance.example.json  semantic.hospital.yml   ← example configs for the two optional features
  test_*.py               23 assert-based test scripts run directly (`uv run python test_x.py`)

frontend/                 React 19 + Vite 6 + Tailwind 4, package manager = bun
  src/App.tsx             single sendQuestion() flow; history, abort/timeout, persistence
  src/components/         ChatArea, ChatMessage (pagination + CSV in ResultsTable), Sidebar
                          (real file upload), Header (live health badge), Settings, ...
  src/lib/                storage.ts (localStorage), csv.ts (RFC-4180 export)
  src/types.ts            response types (incl. results_truncated / latency_ms / row_cap)
```

## The live API contract (`api/endpoints.py`)

- `POST /chat/` — **multipart form**. Fields: `question` (required), a DB reference
  (`connection_id` | `db_file` upload | `db_path` server-absolute path | `db_url` |
  `db_connection_string`), optional `history` (JSON array of last turns `{question, answer,
  sql}`, max 5 kept). Returns `{ answer, sql, results, follow_up_questions,
  results_truncated, sql_executed, validator_rejected, latency_ms }`.
- `POST /schema/` — extract & cache schema only (same DB-reference fields).
- `POST /schema/graph/` — nodes + edges (FK + inferred joins) for the visual explorer;
  capped at 200 nodes with `truncated: true`.
- `GET/POST /connections/`, `DELETE /connections/{id}`, `POST /connections/{id}/check` —
  saved-connection registry; full connection strings NEVER leave the server (masked URIs
  only). Creating a connection runs the preflight; failures are rejected with the
  structured error.
- `GET /llm/models`, `POST /llm/model` `{model}`, `DELETE /llm/model` — which models the
  configured provider serves and which one is picked. The provider (base URL + key) stays
  operator config from `.env`; only the model id changes, persisted to
  `DATATALKER_DATA_DIR/model_selection.json` and applied by `llm/factory.get_provider()`.
- **Bring-your-own-key headers** — any data route accepts `X-LLM-Provider`
  (`gemini|openrouter|openai`) + `X-LLM-Key` (+ optional `X-LLM-Model`), bound to that
  request by `LlmCredentialsMiddleware` and cleared on exit. Base URLs come from a fixed
  preset map, so a caller cannot steer this server to an endpoint of their choosing; an
  unknown provider is a 400 rather than a silent fallback to the operator's key.
- `GET /schema/cache`, `DELETE /schema/cache` — inspect / clear the schema cache.
- `GET /` (info), `GET /health` (readiness: 200 with `llm_mode` = `operator-or-byok` or
  `byok-only` — an instance with no operator key is a supported shape, not a failure —
  and `auth` = `required|disabled`; 503 only when settings cannot load).

DB reference resolution priority (`api/dependencies.py`): explicit refs > `connection_id`.
- `db_path` = an **absolute path on the SERVER's filesystem**, confined to
  `DATATALKER_DB_DIR` (default `backend/`). The frontend's default tab uploads the actual
  file (`db_file`) instead — server paths are an "Advanced" option.
- Any SQLAlchemy URL is accepted: `sqlite:///abs/path`, `postgresql://`, `mysql://` built
  in; other dialects (mssql/oracle/snowflake/…) work when the optional driver extra is
  installed (`uv sync --extra mssql|oracle|snowflake|all`); missing drivers produce a clear
  400 naming the extra.
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
masking is applied to result rows before they leave `query_service`. For schemas larger than
`DATATALKER_MAX_PROMPT_TABLES` (default 25), `core/schema_retrieval.py` scores tables against
the question and sends only the top-K plus their 1-hop graph neighbors (`core/schema_graph.py`),
with a pruning note so the model knows more exists.

## Configuration (all env-driven via `core/settings.py`, prefix `DATATALKER_`)

`DATATALKER_API_TITLE/VERSION, DATATALKER_CORS_ORIGINS` (alias `CORS_ALLOWED_ORIGINS`),
`DATATALKER_CACHE_TTL_SECONDS=3600, DATATALKER_ALLOWED_UPLOAD_EXTENSIONS=.db,.sqlite,.sqlite3,
DATATALKER_MAX_UPLOAD_MB=100, DATATALKER_DB_DIR, DATATALKER_MAX_QUERY_ROWS=500,
DATATALKER_STATEMENT_TIMEOUT_SECONDS=30, DATATALKER_RATE_LIMIT_REQUESTS=30 (0=off),
DATATALKER_RATE_LIMIT_WINDOW_SECONDS=60, DATATALKER_AUDIT_LOG_PATH=logs/audit.log (""=off),
DATATALKER_GOVERNANCE_FILE="" , DATATALKER_SEMANTIC_FILE=""`. LLM config (no prefix):
`LLM_PROVIDER=gemini|openrouter|openai`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`
(`openrouter` fixes its own base URL; only `openai` supplies one). A model picked through
`POST /llm/model` overrides `LLM_MODEL` at runtime.

## Definition of done for changes here

- Verify against the **live** path (`main:fastapi_app` + a fixture DB), not just unit tests.
- Prefer **deletion/consolidation** over adding another way to do something.
- Don't reintroduce doc/reality drift: if you change behavior, update this file and the audit.
- Test changes as assert-based scripts in `backend/test_*.py` (run directly with
  `uv run python test_x.py`; there is no pytest).
