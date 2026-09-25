# DataTalker

**Chat with your database in natural language.** Ask a question in plain English; DataTalker
reflects your schema, has an LLM write the SQL, executes it **read-only** through a safety
pipeline, and answers with plain English + the SQL + the result table.

```
You:  How many patients were admitted last month, by department?
DataTalker:
  Answer: 42 patients were admitted last month. Cardiology led with 15 …
  SQL:    SELECT d.name, COUNT(*) FROM admissions a JOIN departments d …
  Rows:   ▦ paginated result table (CSV export)
```

## Highlights

- **Any database** — SQLite, PostgreSQL, and MySQL out of the box; anything else
  SQLAlchemy speaks (SQL Server, Oracle, Snowflake, …) via optional driver extras. Attach by
  file upload, server path, URL, or connection string — with a **preflight check** that
  verifies the connection, reports server version, dialect, and table count before you query.
- **Scales to big schemas** — a schema graph (tables + foreign keys + inferred joins) with
  relevance pruning: only the tables that matter to your question are shown to the LLM, plus
  their join neighbors. Hundreds of tables stay workable.
- **Connection manager** — save hundreds of named connections server-side, re-run preflight
  checks, switch databases from the UI without re-attaching.
- **Safety pipeline** — API-key auth, rate limiting, single read-only `SELECT` allowlist,
  SQLite `query_only` pin, hard row cap, statement timeouts, path confinement, secret
  redaction, and a JSONL audit log of every question asked.
- **Governance-lite** — optional table allowlist + column masking (full/partial/hash);
  **semantic layer** — optional YAML glossary of descriptions, synonyms, and metric
  definitions that steers the LLM.
- **Pluggable LLM** — Google Gemini, **OpenRouter** (`LLM_PROVIDER=openrouter`, one key in
  front of its whole model catalog), or any OpenAI-compatible endpoint (OpenAI, Azure, vLLM,
  Ollama, LiteLLM) via `LLM_PROVIDER=openai`. Pick the model from the Settings panel — the
  list comes from the provider itself, and the choice applies to the next question.
- **Bring your own key** — a deployed instance needs **no model key of its own**. Each
  visitor can paste their OpenRouter / Gemini / OpenAI key in Settings; it travels as a
  request header, is held in their browser, and the server keeps it for that request only —
  never written to disk, never in the audit log, never echoed back. Without a visitor key it
  falls back to the operator's configured one.
- **Self-hostable** — one Docker image, one volume, your keys, your data.

## Quick start (self-host, one container)

```bash
# 1. Configure (two env vars are required)
cat > backend/.env <<'EOF'
DATATALKER_API_KEY=<run: python -c "import secrets; print(secrets.token_urlsafe(32))">

# One of these three LLM configurations:
GEMINI_API_KEY=your-google-ai-studio-key                                  # default provider
# LLM_PROVIDER=openrouter   + LLM_API_KEY=sk-or-...                      # any OpenRouter model
# LLM_PROVIDER=openai       + LLM_API_KEY/LLM_BASE_URL/LLM_MODEL         # OpenAI/Azure/vLLM/Ollama
EOF

# 2. Build the frontend (or skip and use the API directly)
cd frontend && bun install && bun run build && cd ..

# 3. Run
docker compose up --build
# API on http://localhost:8000 — send: Authorization: Bearer $DATATALKER_API_KEY
```

### Run without Docker

```bash
cd backend && uv sync
uv run uvicorn main:fastapi_app --port 8000

cd frontend && bun install && bun run dev   # http://localhost:5173
```

### On a PaaS (Fly, Render, Railway, Koyeb, Rollout, …)

Point it at this repo — the root `Dockerfile` is auto-detected — and set the **listening
port to 8000**. Attach a persistent volume if you want saved connections and the audit log to
survive a redeploy; skip the managed-Postgres/Redis/S3 add-ons, this app has no app-database.
For a public instance where every visitor brings their own model key, set no `LLM_*` vars and
`DATATALKER_REQUIRE_API_KEY=false`.

## Using it

1. Open the UI → **Connections** → add a connection (paste a URL like
   `postgresql://user:pass@host/db` or upload a `.db` file) → it runs a preflight check and
   shows what it found.
2. Ask questions in the chat. Follow-ups keep context. Answers show the SQL and the rows.
3. Explore the **Schema** view: tables, columns, and how they connect (foreign keys +
   inferred joins).
4. Want a different model? **Settings → Model** lists what your provider serves (an
   OpenRouter or OpenAI-compatible key exposes its whole catalog) — the choice is stored
   server-side and applies to the next question. `RESET` falls back to `LLM_MODEL`.

### Configuration (env vars, prefix `DATATALKER_`)

| Variable | Default | Purpose |
|---|---|---|
| `DATATALKER_API_KEY` | — (required) | Shared secret clients send as `Authorization: Bearer` |
| `DATATALKER_REQUIRE_API_KEY` | `true` | Set `false` to open the data routes on a public bring-your-own-key instance — anyone who finds the URL can then query it |
| `DATATALKER_DB_DIR` | `backend/` | Where server-path SQLite files must live |
| `DATATALKER_MAX_QUERY_ROWS` | `500` | Hard server-side row cap |
| `DATATALKER_RATE_LIMIT_REQUESTS` | `30` / `60s` | Per-IP rate limit (0 = off) |
| `DATATALKER_MAX_PROMPT_TABLES` | `25` | Schema-retrieval budget for huge schemas (0 = all) |
| `DATATALKER_DATA_DIR` | `backend/data` | Connections registry storage |
| `DATATALKER_AUDIT_LOG_PATH` | `backend/logs/audit.log` | JSONL audit log ("" = off) |
| `DATATALKER_GOVERNANCE_FILE` | — | JSON: allowed tables + masked columns |
| `DATATALKER_SEMANTIC_FILE` | — | YAML glossary: descriptions, synonyms, metrics |

LLM (no prefix): `LLM_PROVIDER=gemini|openrouter|openai`, `LLM_MODEL`, `LLM_API_KEY`,
`LLM_BASE_URL` (only `openai` needs a base URL; `openrouter` pins its own). Model choice from
the UI overrides `LLM_MODEL` at runtime (`GET /llm/models`, `POST|DELETE /llm/model`).

**Bring your own key** (no operator LLM config needed): send `X-LLM-Provider`
(`gemini|openrouter|openai`) and `X-LLM-Key` on any data route. The key is used for that
request alone — never cached, never logged, never returned — and the provider's base URL is
chosen by preset, so a caller cannot point your server at an arbitrary endpoint.

### Optional database drivers

```bash
uv sync --extra mssql      # pyodbc  -> SQL Server (mssql://…)
uv sync --extra oracle     # oracledb
uv sync --extra snowflake  # snowflake-sqlalchemy
```

## Security model (read before exposing it)

DataTalker is designed as a **single-tenant, self-hosted analyst tool**, not a multi-user
SaaS. The generated SQL is constrained to a single read-only `SELECT` and executed on a
read-only engine where the dialect allows it — but the *strongest* guarantee comes from
connecting with a **least-privilege, read-only database role**. Connection strings are stored
server-side in `DATATALKER_DATA_DIR/connections.json` for self-hosted convenience; don't use
the registry on a machine you don't control. Every question + generated SQL is appended to
the audit log.

## Project layout

- `backend/` — FastAPI app (`main.py` → `api/` → `services/` → `graphs/` → `agents/` → `llm/`/`core/`).
  `CLAUDE.md` is the detailed working guide; `docs/CODEBASE_AUDIT.md` tracks the security/quality roadmap.
- `frontend/` — React 19 + Vite + Tailwind 4 SPA.

## Development

```bash
cd backend && for t in test_*.py; do uv run python "$t"; done   # 20+ assert-based test scripts
```

License: MIT.
