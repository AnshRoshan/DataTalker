# CLAUDE.md — DataTalker

> Working guide for AI agents and humans. Written from a verified 36-agent audit of the
> actual code (2026-07-04), not from the aspirational docs. Where this file and
> `backend/ARCHITECTURE.md` / `backend/ENTERPRISE_TRANSFORMATION_PLAN.md` disagree, **this
> file is correct** — those docs describe things that were never wired up (see below).
>
> Full findings + productionization roadmap: **[`docs/CODEBASE_AUDIT.md`](docs/CODEBASE_AUDIT.md)**.

## What this is

DataTalker is a "talk to your data" app: ask a natural-language question, it reflects a
database's schema, uses an LLM (Google Gemini) to write SQL, executes it, and returns a
plain-English answer + the SQL + the result rows. FastAPI backend + React/Vite (TypeScript)
frontend.

**Status: Phase-1 hardened prototype (merged to main).** Still single-tenant and hardwired to
one LLM vendor + two DB dialects — not yet enterprise-*featured*, but now enterprise-*safe*.
Phase 1 added API-key auth, a read-only single-`SELECT` allowlist on a read-only engine,
`db_path` confinement + `db_url` SSRF guard, threadpool offload, error/secret sanitization, a
schema-cache TTL, and structured logging with correlation IDs. See `docs/CODEBASE_AUDIT.md`
(Phase-1 status banner) for exactly what's fixed vs open.

## ⚠️ Read this first: there are THREE parallel backends. Only ONE runs.

This is the single biggest source of confusion in the repo. ~6× more backend orchestration
code is **dead** than alive.

| Stack | Entry point | Status | Touch it? |
|---|---|---|---|
| **① Live / modular** | `backend/main.py` → `api/` → `services/` → `graphs/` → `agents/` → `llm/gemini.py` | **This is what actually runs and serves the frontend.** | ✅ All real work happens here |
| **② "Enterprise"** | `backend/enterprise_app.py`, `enterprise_graph.py`, `enterprise_status.py`, top-level `main_graph.py`, `core/{auth,security,middleware,monitoring,tasks,task_implementations}.py` | **Dead. ~4,000 LoC. Does not even compile** (`enterprise_app.py:195` IndentationError; broken imports; deps like celery/redis/jwt not installed). Imported only by the test suite. | ❌ Delete or quarantine — do not "fix in place" |
| **③ Legacy** | `backend/streamlit.py` (Streamlit UI), `backend/work.py` (empty, 0 bytes) | Superseded by the React frontend. | ❌ Delete or move to `legacy/` |

The `Dockerfile` and `docker-compose*.yml` deploy stack ②, so **`docker compose up` produces
a crash-looping container** — there is currently no container target that runs the live app.
The test suite (`backend/tests/`) also targets stack ② and cannot even be collected. So:
**there is effectively zero automated test coverage of the shipped app.**

## Repo layout (what's real)

```
backend/
  main.py                 ① LIVE entry — uvicorn main:fastapi_app on :8000
  api/
    endpoints.py          ① the 6 real routes (see contract below)
    dependencies.py       ① resolves db_file / db_path / db_url / db_connection_string
    models.py             ⚠ Pydantic models declared but NOT enforced (handlers return raw dicts)
  services/
    schema_service.py     ① schema extraction + cache orchestration
    query_service.py      ① NL→SQL orchestration, shapes the response
  graphs/
    query_graph.py        ① LIVE LangGraph: writer→validator→executor→(retry)→formatter
    schema_graph.py       ① LIVE single-node schema-reflection graph
    main_graph.py         ✗ DEAD (compiles main_app; nothing imports it)
  agents/                 ① the 7 pipeline agents (see below)
    sql_writer.py  validator.py  db_executor.py  answer.py
    schema.py  user_input.py  fallback.py  sql_retry.py
  llm/                    ① pluggable LLM layer (EC-01): base.py protocol, providers/
                               (gemini, openai_compat), factory.py (env-driven), prompts.py,
                               service.py (the 2 funcs agents call; retry loop lives here)
  core/
    config.py             ① flat hardcoded constants (CORS=['*'], etc.) — not env-driven
    database.py           ① connection-string parsing + path validation
    cache.py              ① process-global schema cache dict (TTL 3600s)
    file_handler.py       ① upload/download temp-file handling
    auth.py security.py middleware.py monitoring.py tasks.py task_implementations.py  ✗ DEAD (stack ②)
  Database/
    PopulateDB.py         Faker-based sample-data generator
    HospitalSchema.py     ✗ orphaned SQLAlchemy models (schema-mismatched, unused)
  hospital.db, multi_table.db   ← ready-to-use SQLite fixtures for the LIVE app
  tests/                  ✗ target stack ② (dead); not runnable
  enterprise_*.py, main_graph.py   ✗ DEAD (stack ②)
  streamlit.py, work.py            ✗ legacy (stack ③)

frontend/                 ① React 19 + Vite 6 + Tailwind 4, package manager = bun
  src/App.tsx             top-level state + the request logic (two ~90-line duplicate handlers)
  src/components/         ChatArea, ChatMessage, ResultsTable, Sidebar, Header, InputArea, Settings, ...
  src/types.ts            response types (do NOT model the multi-statement result shape — a bug)
```

## The live API contract (`api/endpoints.py`)

- `POST /chat/` — **multipart form** (not JSON). Fields: `question` (required) + exactly one DB
  reference. Returns `{ answer, sql, results, follow_up_questions }`.
- `POST /schema/` — extract & cache schema only.
- `GET /schema/cache`, `DELETE /schema/cache` — inspect / clear the schema cache.
- `GET /` (info), `GET /health` (static liveness stub — always returns healthy).

DB reference resolution priority (`api/dependencies.py`): `db_connection_string` > `db_path`
> `db_file` > `db_url`.
- `db_path` = an **absolute path on the SERVER's filesystem** (not a browser file). ⚠ The
  frontend's "Local File" tab sends *this*, so browser users can't actually upload their own
  `.db` — see `docs/CODEBASE_AUDIT.md` FE-01.
- `db_connection_string` = `sqlite:///abs/path` or `postgresql://user:pass@host/db`.
- `results` is polymorphic: a flat `list[dict]` for one SELECT, but a **list of wrapper dicts**
  `{statement_index, statement, results, row_count}` for multi-statement SQL — which the
  frontend does not unwrap (renders `[object Object]`). See CORR-3 / FE-02.

## Running it locally

**Backend** (needs `GEMINI_API_KEY` **and now `DATATALKER_API_KEY`** in `backend/.env` — the app
raises at import without the Gemini key and denies every data request without the API key):
```bash
cd backend
# backend/.env (gitignored):
#   GEMINI_API_KEY=...
#   DATATALKER_API_KEY=<a long random secret>   # clients send: Authorization: Bearer <it>
#   DATATALKER_DB_DIR=...   (optional; default backend/ — db_path is confined here)
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
path:
```bash
curl -X POST http://127.0.0.1:8000/chat/ \
  -H "Authorization: Bearer $DATATALKER_API_KEY" \
  -F "question=How many patients are there?" \
  -F "db_path=E:/GENAI-PROJECTS/DataTalker/backend/hospital.db"
```

## The NL→SQL pipeline (stack ①)

`query_graph.py` wires: **SQLWriterAgent** (Gemini writes SQL or decides no SQL is needed) →
**ValidatorAgent** (keyword blocklist safety gate) → **DBExecutorAgent** (runs the SQL via a
per-request SQLAlchemy engine) → optional **SQLRetryAgent** (max 2 retries when results are
empty) → **AnswerFormatterAgent** (Gemini turns rows into a NL answer + follow-up questions).
Schema is reflected once by **SchemaAgent** and cached.

## Landmines — the top things that will bite you

Phase 1 fixed the critical/high security + prod items (per-finding status in
`docs/CODEBASE_AUDIT.md`). Current state:

**Fixed in Phase 1 + Phase 2A** (each has an assert-based test in `backend/test_*.py`):
1. ✅ **SEC-01** — SQL is now an allowlist: a single read-only `SELECT`/`WITH` on a read-only
   engine (`agents/validator.py`, `agents/db_executor.py`). Multi-statement rejected.
2. ✅ **SEC-02 / SEC-06** — API-key auth on all data routes (`DATATALKER_API_KEY`, deny-by-default)
   + CORS locked to explicit origins.
3. ✅ **PR-02** — `/chat/` + `/schema/` are sync `def` → run in Starlette's threadpool.
4. ✅ **SEC-03/04, PR-11** — `db_url` SSRF-guarded; `db_path` confined to `DATATALKER_DB_DIR`;
   size caps; unique temp files.
5. ✅ **PR-05/SEC-05** — generic client errors; secrets/tracebacks to logs only; Gemini key in header.
6. ✅ **CORR-1** — Postgres schema cache now expires via a TTL.
7. ✅ **PR-06** — structured logging + per-request `X-Request-ID` (backbone; legacy prints remain).
8. ✅ **EC-01** — pluggable LLM provider: `LLM_PROVIDER=gemini|openai` + `LLM_BASE_URL`
   runs any OpenAI-compatible endpoint (OpenAI/Azure/vLLM/Ollama/LiteLLM). Gemini stays
   the zero-config default. See `backend/llm/` + `test_llm_{service,factory,providers}.py`.

**Still open (Phase 2+):**
- **Two schema caches** (`core/cache.py` + `SchemaAgent`'s LRU/JSON) can still diverge.
- **PR-03** no engine pooling · **PR-09** no rate limiting · the ~100 `print()` sweep · **ARCH-06** bogus deps.
- Single-tenant; no semantic layer / RBAC / dialects beyond sqlite+postgres (Phase 2 = the PRD).

## Conventions & gotchas when changing code

- **Only edit stack ①.** If you touch `enterprise_*`, `core/{auth,security,middleware,monitoring,
  tasks,task_implementations}`, or top-level `main_graph.py`, you are editing dead code.
- LLM access goes through `llm/service.py` (`generate_sql_or_response` / `format_answer`) —
  never call a provider directly. New providers implement `llm/base.py:LLMProvider` and get
  wired in `llm/factory.py`. Config: `LLM_PROVIDER`/`LLM_MODEL`/`LLM_API_KEY`/`LLM_BASE_URL`.
- `core/config.py` is hardcoded constants; there is **no** pydantic Settings / env loading beyond
  `GEMINI_API_KEY`. Don't assume `.env` / compose env vars take effect — they mostly don't.
- Two dependency manifests (`pyproject.toml` pinned, `requirements.txt` unpinned) drift. `uv` is
  the source of truth (`uv.lock`). Note `pathlib` and `replicate` are bogus/dead deps.
- Python is pinned to **3.13** (`.python-version`), but the `Dockerfile` uses 3.11 — inconsistent.

## Tooling available in this repo

- **code-review-graph** (MCP server, `.mcp.json`) — a local Tree-sitter code graph of this repo
  (~500 nodes). After a Claude Code restart, query it for blast-radius / minimal review context.
  Rebuild manually: `code-review-graph build`. Auto-updates via git pre-commit + PostToolUse hooks.
- **`/graphify`** skill — builds a Claude-powered semantic knowledge graph (good for turning the
  docs/architecture into a queryable map; note it sends non-code content to an LLM).
- **ponytail** plugin — active from next session; nudges toward the smallest correct diff. Fitting,
  given this codebase's #1 issue is over-engineering.

## Definition of done for changes here

- Verify against the **live** path (`main:fastapi_app` + a fixture DB), not the dead tests.
- Prefer **deletion/consolidation** over adding a fourth way to do something.
- Don't reintroduce doc/reality drift: if you change behavior, update this file and the audit.
