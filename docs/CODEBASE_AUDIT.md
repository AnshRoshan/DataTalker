# DataTalker — Codebase Audit & Productionization Roadmap

**Date:** 2026-07-04 · **Method:** 36-agent automated audit (6 subsystem maps → 6 problem
dimensions → adversarial verification of every critical/high finding against the real code).
**Scope:** entire repo — backend (FastAPI, ~11.4k LoC Python) + frontend (React/Vite, ~1.8k LoC).

> Each finding was cross-checked by an independent skeptic agent instructed to *refute* it.
> 23 severe findings were **confirmed**, 1 was **downgraded** (PR-04) as overstated. The
> summary below reflects those verdicts.

> **⚠️ Phase 1 status update (fixed on branch `phase1-harden`, merged to main):** the
> critical/high **security + production** findings are resolved — **SEC-01, SEC-02, SEC-03,
> SEC-04, SEC-05, SEC-06, PR-01, PR-02, PR-05, PR-06, PR-10, PR-11, CORR-1, CORR-2, CORR-3**
> (+ FE-02's data half), **ARCH-01/03/05** — each with an assert-based test in `backend/test_*.py`.
> **⚠️ Phase 2 status update (fixed on branch `phase2-pluggable-llm`):** **EC-01** (pluggable
> LLM provider) is resolved — see finding below.
> **Still open:** the rest of the Phase-2 enterprise-fit items, PR-03 pooling,
> PR-08 readiness, PR-09 rate limiting, ARCH-06 deps, the `print()` sweep, and the frontend (FE-*).

---

## 1. Executive summary

DataTalker is a **working single-user prototype** of an LLM-powered "talk to your data" tool.
The core idea works: it reflects a schema, Gemini writes SQL, it runs and explains the result.
But measured against the stated goal — *"a best-in-class, highly customizable NL→SQL product any
enterprise can point at their data"* — it is not close, and the gap is not mainly about polish.
It is about four structural facts:

1. **It is unsafe.** LLM-authored SQL is executed as a raw string, gated only by a keyword
   blocklist that misses arbitrary-file-read / RCE vectors, on endpoints with **no
   authentication**. (SEC-01, SEC-02)
2. **It cannot scale as built.** Every request is synchronous work run on the async event loop
   with no offload, so the server is effectively single-threaded and one slow LLM call stalls
   everything. (PR-02)
3. **It is not customizable.** The prompts, the SQL-safety rules, the two DB dialects, and the
   (nonexistent) tenant boundary are all frozen in Python literals. (EC-02…10; the LLM vendor
   itself is no longer frozen — EC-01 fixed on `phase2-pluggable-llm`.)
4. **It is not honest with itself.** ~4,000 lines of a dead "enterprise" stack that *doesn't
   compile* — plus a test suite and Docker/compose files that all target it — create a false
   impression of auth, scale, and monitoring that do not exist. The docs promise "1000 concurrent
   users / Redis / Celery / JWT / Prometheus"; none of it is wired. (ARCH-01, PR-01, ARCH-05)

**The good news:** the live path is small (~666 LoC of orchestration), the agent/graph
decomposition is a sound backbone, there are usable SQLite fixtures, and most fixes are additive
seams rather than rewrites. This is very salvageable — the first job is to *delete the fiction*
and *make the real thing safe*, then grow the customization seams.

### Verified severity counts

| Dimension | Critical | High | Medium | Low | Total |
|---|---:|---:|---:|---:|---:|
| Security | 2 | 3 | 3 | 0 | 8 |
| Correctness | 0 | 1 | 3 | 4 | 8 |
| Architecture | 0 | 2 | 5 | 2 | 9 |
| Production-readiness | 2 | 3 | 5 | 1 | 11 |
| Enterprise-customizability | 3 | 5 | 2 | 0 | 10 |
| Frontend / API contract | 0 | 2 | 5 | 4 | 11 |
| **Total** | **7** | **16** | **23** | **11** | **57** |

### The 7 criticals (fix before any exposure)

| ID | Title | Where |
|---|---|---|
| **SEC-01** | LLM SQL run as raw `text()`; blocklist misses `ATTACH`/`COPY TO PROGRAM`/`pg_read_file` → file read / RCE | `agents/db_executor.py:76`, `agents/validator.py:7` |
| **SEC-02** | No auth/authz on any live endpoint | `api/endpoints.py:20` |
| **PR-01** | Docker/compose deploy the dead enterprise app → crash-loop; no target runs the live app | `Dockerfile:44`, `docker-compose.yml` |
| **PR-02** | `async` handlers block the event loop on sync SQL + LLM | `services/query_service.py:38` |
| **EC-01** | ✅ *Fixed* — LLM hardwired to Gemini; no provider/model abstraction | `backend/llm/` |
| **EC-04** | No multi-tenancy / per-tenant isolation; schema cache is one global | `core/cache.py` |
| **EC-05** | No RBAC / row-level security / column masking; governance = bypassable blocklist | `agents/validator.py:7` |

---

## 2. The "three stacks" problem (root cause of most architecture debt)

The repo contains three mutually-incompatible backends over the same 7 agents:

- **① Live/modular** (`main.py → api → services → graphs → agents → llm`): synchronous,
  unauthenticated, single-tenant. **This is what ships.**
- **② "Enterprise"** (`enterprise_app.py`, `enterprise_graph.py`, `enterprise_status.py`,
  top-level `main_graph.py`, `core/{auth,security,middleware,monitoring,tasks,task_implementations}`):
  ~4,007 LoC, **does not compile** (`enterprise_app.py:195` IndentationError; `enterprise_graph.py:17`
  imports a symbol that doesn't exist; `get_settings` imported by 7 modules but never defined; deps
  celery/redis/jwt/passlib/structlog absent). Imported only by `tests/`.
- **③ Legacy** (`streamlit.py`, `work.py` [0 bytes]): superseded by the React frontend.

Consequence: dead-to-live orchestration ratio ≈ **6:1**; `docker compose up` crash-loops; the test
suite can't be collected; and the docs cite ② as evidence of production features. **Recommended
first action: delete ② and ③ (or move ② to an `experimental/` branch) and their tests.** Do not
try to repair ② in place — it has never run.

---

## 3. Findings by dimension

Severity in brackets; `→` shows any severity change from adversarial verification.

### 3.1 Security

- **[CRITICAL] SEC-01 — Raw LLM SQL execution + weak blocklist.** `db_executor.py:76` runs
  `connection.execute(text(statement))` on caller-controlled SQL, split on `;` (multi-statement).
  The only gate is `validator.py:7-19`, a lowercase word-boundary blocklist of DML/DDL verbs — it
  does **not** block SQLite `ATTACH`/`PRAGMA` or Postgres `COPY (…) TO PROGRAM` / `pg_read_file` /
  `pg_ls_dir`. On a privileged Postgres role this is arbitrary file read and potential command
  execution. `EnhancedValidatorAgent` (`validator.py:97-140`) has injection checks but is **never
  instantiated**. *Fix:* enforce read-only at the engine/role layer (SQLite `mode=ro`, Postgres
  `SET TRANSACTION READ ONLY` + a least-privilege role), reject multi-statement, parse with
  `sqlglot` and allow only single `SELECT`s against known tables, add `statement_timeout`.
- **[CRITICAL] SEC-02 — No authentication on any wired route.** `api/endpoints.py:20-153` has no
  `Depends`/`Security`. The server binds `0.0.0.0:8000`. Every other vuln here is reachable
  anonymously. *Fix:* auth dependency / gateway / mTLS on all data routes; stop treating the
  client bearer as decorative.
- **[HIGH] SEC-03 — SSRF via `db_url`.** `file_handler.py:56` does `requests.get(db_url)` with no
  scheme/host allowlist, no private-IP block, follows redirects, buffers unbounded body → internal
  service / cloud-metadata (`169.254.169.254`) reachability + memory-exhaustion. Predictable temp
  name races too. *Fix:* allowlist, reject private/link-local (incl. post-redirect), streamed byte
  cap, `tempfile.mkstemp`.
- **[HIGH] SEC-04 — Arbitrary local file access via `db_path`.** `database.py:32` only checks
  absolute + exists + isfile — **no directory confinement**. Any absolute server path becomes
  `sqlite:///…`. *Fix:* confine to an allowlisted base dir (realpath + prefix), or remove
  server-path input in favor of real uploads.
- **[HIGH] SEC-05 — Secret & internals leakage.** `/schema/` returns `database_uri` verbatim (Postgres
  password echoed to client, `endpoints.py:54`); `db_executor.py:62` prints the URI; Gemini API key
  is sent as a **URL query param** (`gemini.py:189,328`) so it lands in logs/proxies; raw
  `str(e)` + `traceback.format_exc()` + generated SQL flow back to callers. *Fix:* redact creds,
  omit URI from responses, use `x-goog-api-key` header, generic client errors + server-side logs.
- **[MEDIUM] SEC-06 — CORS `['*']` + `allow_credentials=True`** (`config.py:23`). Invalid/unsafe
  combo; with no auth, any origin can drive the API (CSRF surface on the state-changing POSTs/DELETE).
- **[MEDIUM] SEC-07 — Prompt injection into generated SQL.** Question + attacker-supplied schema
  (table/column names) are concatenated into the prompt (`gemini.py:172`); a successful injection
  yielding a SELECT passes the blocklist. *Fix:* delimit untrusted content, validate generated SQL
  against the reflected schema.
- **[MEDIUM] SEC-08 — DoS: no row cap / query timeout / upload+download size limit; sync handlers.**
  `db_executor.py:82` materializes the full result set; `LIMIT` is only *suggested* to the LLM;
  `MAX_FILE_SIZE` defined but unenforced. *Fix:* hard server-side row cap, statement timeout, size
  caps, threadpool offload, rate limiting.

### 3.2 Correctness

- **[HIGH] CORR-1 — Postgres schema cache never invalidates.** `SchemaAgent` only does mtime
  staleness for SQLite; for Postgres `path_for_mod_time_check=None`, so the on-disk JSON cache
  (`~/.text_to_sql_schema_cache`) is valid **forever**, surviving restarts. DDL changes are never
  seen → wrong SQL / missing-column errors indefinitely. (`schema.py:122,426`) *Fix:* TTL or a cheap
  catalog fingerprint for non-file DBs.
- **[MEDIUM] CORR-2 — Predictable temp filenames collide across concurrent requests** (`talkdb_*_<pid>`,
  `file_handler.py:61`) → one request reads another's DB. *Fix:* `tempfile.mkstemp`.
- **[MEDIUM] CORR-3 — Multi-statement results render as a garbled meta-table** (`[object Object]`).
  Backend returns wrapper dicts; frontend never unwraps them. (`db_executor.py:91`, `ResultsTable.tsx:24`)
- **[MEDIUM] CORR-4 — Full Python tracebacks/SQL leak into the chat answer** (`db_executor.py:150` →
  `answer.py:34`). *Fix:* sanitize user-facing, log detail server-side.
- **[LOW] CORR-5 — Broken fence-strip regex** (`\\s` literal instead of `\s`, `gemini.py:89`) →
  fenced JSON always hits the greedy fallback parser.
- **[LOW] CORR-6 — DML would silently roll back** (no `commit`; SQLAlchemy 2.0 commit-as-you-go) while
  reporting `affected_rows` — latent, masked by the validator today. (`db_executor.py:69`)
- **[LOW] CORR-7 — Dead non-array results filter in `App.tsx:114`** (backend always returns an array).
- **[LOW] CORR-8 — Retry that yields a direct answer leaves `sql_executed` stale**, mis-routing the
  formatter. (`sql_retry.py:59`)

### 3.3 Architecture

- **[HIGH] ARCH-01 — ~4,000 LoC dead enterprise stack that doesn't compile.** (see §2) *Fix:* delete
  or quarantine.
- **[HIGH] ARCH-02 — Async handlers call fully synchronous blocking pipelines** with no threadpool
  offload → per-worker serialization. (`query_service.py:38`, `schema_service.py:41`) *Fix:* declare
  routes `def` (auto-threadpool) **or** wrap `invoke` in `run_in_threadpool`/`asyncio.to_thread`;
  longer term go async DB + async LLM client.
- **[MEDIUM] ARCH-03 — Three graph builders for the same 7 agents** (`graphs/main_graph.py` dead,
  top-level `main_graph.py` dead, only `query_graph`+`schema_graph` live).
- **[MEDIUM] ARCH-04 — Split, incompatible config contract**; hardcoded constants vs the enterprise
  stack's expected nested `Settings`/`get_settings` (which don't exist). (`config.py`)
- **[MEDIUM] ARCH-05 — Test suite exercises only the dead stack** — imports `SecurityService`
  (doesn't exist) so it can't even be collected; asserts routes the live app doesn't have. Zero
  coverage of shipped behavior. (`tests/conftest.py:19`)
- **[MEDIUM] ARCH-06 — Two drifting dependency manifests + bogus deps** (`pathlib` backport,
  `replicate`, heavy `streamlit` as a core dep). *Fix:* `pyproject`+`uv.lock` as single source.
- **[MEDIUM] ARCH-08 — Two divergable schema caches** (`core/cache.py` global dict + `SchemaAgent`
  LRU/JSON) with different keys/invalidation; global dict isn't shared across workers.
- **[LOW] ARCH-07 — `response_model` declared but never enforced** (handlers return raw
  `JSONResponse`); `api/models.py` request models unused.
- **[LOW] ARCH-09 — Empty `work.py` + legacy `streamlit.py`** still presented by docs as "the UI".

### 3.4 Production-readiness

- **[CRITICAL] PR-01 — No working container/deploy target** (Docker/compose run the non-compiling
  enterprise app; live app never referenced). *Fix:* add a stage running `uvicorn main:fastapi_app`
  (gunicorn+uvicorn workers) and repoint compose.
- **[CRITICAL] PR-02 — Event-loop blocking** (see ARCH-02; worst case 180s+ of blocking per request
  from LLM timeouts+backoff).
- **[HIGH] PR-03 — New engine created & disposed per request** (`db_executor.py:64`) → no real
  pooling; every Postgres query pays a full connect+auth. *Fix:* cache engines per `db_uri` with a
  bounded `QueuePool` + `pool_pre_ping`.
- **[HIGH] PR-05 — Internal errors/tracebacks leaked to clients** (`endpoints.py:67`, `query_service.py:59`,
  `schema_service.py:46`). *Fix:* generic error + correlation ID.
- **[HIGH] PR-06 — Unobservable live path** — no logging (`import logging` absent from api/services/
  graphs/agents), ~100 `print()`s, no correlation IDs, no real metrics. *Fix:* structured JSON logs +
  request-ID middleware; redact SQL/schema.
- **[LOW] PR-04 — Global schema-cache dict** — *downgraded from High:* the `--workers 4` command runs
  the (dead) enterprise app, so the real single-worker app never hits the multi-worker divergence
  scenario. Still a smell; fix when scaling.
- **[MEDIUM] PR-07 — Config hardcoded, documented env vars ignored** (`config.py`).
- **[MEDIUM] PR-08 — `/health` is a static stub** (no readiness check; Docker/compose gate on it).
- **[MEDIUM] PR-09 — No rate limiting on routes that trigger paid LLM calls + arbitrary SQL** →
  financial + availability DoS.
- **[MEDIUM] PR-10 — Deploy artifacts inconsistent** — Python 3.11 image vs `requires-python>=3.13`;
  compose mounts a nonexistent `nginx/` dir; hardcoded default `SECRET_KEY`/DB creds.
- **[MEDIUM] PR-11 — Unbounded uploads, leaked/kept temp files, predictable download collisions.**

### 3.5 Enterprise-customizability (the "make it a product" gaps)

- **[CRITICAL] EC-01 — LLM hardwired to Gemini** (model IDs are string literals; key read at import;
  agents import the concrete function). Blocks Azure OpenAI / Bedrock / Vertex / on-prem — usually a
  hard requirement for enterprises to allow an NL→SQL tool near their data. *Fix:* `LLMProvider`
  protocol + factory driven by config; first adapters Gemini + OpenAI-compatible (covers Azure/vLLM/
  LiteLLM/Bedrock-gateway). Consider LiteLLM.
  ✅ **Fixed on branch `phase2-pluggable-llm`:** provider protocol + gemini/openai_compat adapters
  + env-driven factory; `llm/gemini.py` deleted.
- **[CRITICAL] EC-04 — No multi-tenancy / per-tenant isolation** (zero `tenant`/`org` concept; one
  global schema cache). *Fix:* tenant/principal context (from auth) threaded into services/agents;
  key cache + per-tenant config (model/prompts/allowlist/connection) by `tenant_id`.
- **[CRITICAL] EC-05 — No RBAC / RLS / column masking** — governance is the bypassable blocklist;
  any caller reading `/chat/` can read every column of every visible table. *Fix:* authz principal+role
  → filter LLM-visible schema (EC-06) + post-generation allow-model on the SQL (sqlglot: verify
  tables/columns permitted, inject mandatory RLS predicates, mask protected columns).
- **[HIGH] EC-02 — Prompts hardcoded** in Python literals (`gemini.py:47,280`); no template/registry/
  per-tenant override (plus leftover `{{ }}` `.format` artifacts). *Fix:* externalize to templated
  files + a per-deployment "system addendum".
- **[HIGH] EC-03 — Only SQLite + Postgres** (`config.py:15`); unknown dialects default to SQLite
  syntax. Excludes Snowflake/BigQuery/Redshift/Databricks/MySQL/SQL Server. *Fix:* dialect registry
  keyed by SQLAlchemy dialect (prompt snippet + quoting + driver per entry).
- **[HIGH] EC-06 — No table/column allowlist wired** — `SchemaAgent` exposes the entire reflected
  schema; the `include_tables` seam exists but nothing on the live path populates it. *Fix:* promote
  to a config/tenant-driven allowlist + `masked_columns`, resolved in the service layer.
- **[HIGH] EC-07 — No config surface (YAML/env)** — behavior frozen in constants. *Fix:* pydantic-
  settings covering llm / dialects / prompts / governance / limits / cors.
- **[HIGH] EC-08 — No audit log of who-asked-what** — only ephemeral `print()`s; no identity to
  attribute. Fails SOX/HIPAA/GDPR-style review. *Fix:* append-only structured audit record per
  request (principal, tenant, question, SQL, verdict, rows, target DB, latency).
- **[MEDIUM] EC-09 — No semantic layer / business glossary / metric definitions** — LLM sees only raw
  physical schema, so it guesses on opaque names → subtly wrong numbers. *Fix:* optional per-tenant
  semantic model (descriptions, synonyms, metric SQL, join paths); consider dbt/Cube interop.
- **[MEDIUM] EC-10 — Result caps & safety blocklist hardcoded/unenforced** (`MAX_QUERY_RESULTS`
  doesn't exist; `LIMIT` only suggested; `MAX_FILE_SIZE` unenforced). *Fix:* make them config + hard
  server-side enforcement.

### 3.6 Frontend / API contract

- **[HIGH] FE-01 — The "Local File" tab can't upload a browser file.** The Browse button only
  `alert()`s; the app always sends `db_path` (a **server** path), never `db_file` — which the backend
  supports. Browser users literally cannot query their own DB. (`Sidebar.tsx:35`, `App.tsx:88`) *Fix:*
  read `files[0]` → `formData.append('db_file', file)`; keep manual path as an "advanced: server path".
- **[HIGH] FE-02 — Multi-statement results show metadata + `[object Object]`** (mirror of CORR-3;
  `ResultsTable.tsx:24`). *Fix:* detect the wrapper shape, render each statement's `.results` as its
  own table; `JSON.stringify` fallback for object cells; fix `types.ts` union.
- **[MEDIUM] FE-03 — `Authorization: Bearer` sent + API key in plaintext `localStorage`, backend
  ignores it** (security theater). (`App.tsx:99`, `Settings.tsx`)
- **[MEDIUM] FE-04 — No request timeout, no streaming, no cancel** — a slow round-trip hangs behind a
  spinner indefinitely. (`App.tsx:106`)
- **[MEDIUM] FE-05 — `handleSubmit` and `handleFollowUpClick` are ~90-line copy-paste duplicates**
  (`App.tsx:52` vs `:155`). *Fix:* extract one `sendQuestion(question)`.
- **[MEDIUM] FE-06 — Error banner's ✕ clears the input box, not the error** (`InputArea.tsx:27`) —
  destroys the user's question.
- **[MEDIUM] FE-07 — No pagination/virtualization** — every row → DOM node with per-row hover +
  animation delay; big results freeze the tab. (`ResultsTable.tsx:186`)
- **[LOW] FE-08 — Header "Connected"/"FastAPI" badges are hardcoded**, never reflect real health.
- **[LOW] FE-09 — Chat history/DB selection not persisted** — reload wipes everything.
- **[LOW] FE-10 — Message ids use `Date.now()`** → possible React key collisions on rapid clicks.
- **[LOW] FE-11 — Dead `.error` fallback + response types that don't match the contract.**

---

## 4. Productionization & customization roadmap

Sequenced so each phase is independently shippable. Phase 0 is non-negotiable before *any*
exposure to untrusted input or real data.

### Phase 0 — Make it honest & safe (days)
1. **Delete the fiction:** remove stack ② (`enterprise_*`, top-level `main_graph.py`,
   `core/{auth,security,middleware,monitoring,tasks,task_implementations}`) and its tests, or move to
   an `experimental/` branch. Delete `work.py`; decide `streamlit.py`'s fate. Fix/replace
   `ARCHITECTURE.md`. → clears ARCH-01/03/05, PR-01 (partly).
2. **Lock the SQL execution surface:** read-only least-privilege DB role, single-`SELECT`-only via
   `sqlglot`, reject multi-statement, `statement_timeout`, hard row cap. Wire (or replace) the
   validator. → SEC-01, SEC-08, EC-10, CORR-6.
3. **Add authentication** (API key/JWT dependency) + per-IP rate limiting in front of all data
   routes. → SEC-02, PR-09.
4. **Stop leaking:** generic client errors + correlation IDs; redact creds from responses/logs;
   Gemini key via header. → SEC-05, PR-05, CORR-4.
5. **Constrain inputs:** allowlist `db_path` base dir + `db_url` hosts (block private IPs); enforce
   upload/download size caps; `tempfile.mkstemp`. → SEC-03, SEC-04, PR-11, CORR-2.

### Phase 1 — Make it production-shaped (1–2 weeks)
6. **Un-block the event loop:** `run_in_threadpool` for `invoke` now; plan async DB/LLM later. →
   PR-02, ARCH-02.
7. **Real deploy:** Dockerfile stage running the live app on Python 3.13, gunicorn+uvicorn workers,
   compose pointed at it, real readiness probe, secrets from env. → PR-01, PR-08, PR-10.
8. **Engine pooling** cached per `db_uri`; **single** schema-cache owner (optionally Redis-backed). →
   PR-03, ARCH-08, CORR-1 (add TTL/fingerprint for Postgres).
9. **Observability:** structured JSON logging + request IDs; replace `print()`; basic metrics. → PR-06.
10. **A minimal real test suite** against the live `/chat/` + `/schema/` using `hospital.db`. → ARCH-05.
11. **Config surface:** pydantic-settings for CORS/limits/timeouts/model/key. → PR-07, ARCH-04, SEC-06.

### Phase 2 — Make it a customizable enterprise product (the differentiators)
12. **Pluggable LLM provider** (`LLMProvider` protocol + factory; Gemini + OpenAI-compatible;
    consider LiteLLM). → EC-01. ✅ **Done on `phase2-pluggable-llm`** — see EC-01 above.
13. **Dialect registry** (Snowflake/BigQuery/Redshift/MySQL/SQL Server + per-dialect prompts). → EC-03.
14. **Governance layer:** principal+role → schema allowlist + column masking + post-gen SQL allow-model
    with RLS predicate injection; per-request audit log. → EC-05, EC-06, EC-08.
15. **Multi-tenancy:** tenant context threaded everywhere; tenant-scoped cache + per-tenant config
    (model, prompts, allowlist, connection). → EC-04.
16. **Externalized, layered prompts** + **semantic layer** (glossary/metrics/join hints; dbt/Cube
    interop). → EC-02, EC-09.
17. **Frontend rebuild of the contract:** real file upload, multi-statement rendering, timeout/cancel/
    streaming, de-duplicated handlers, pagination, persisted history, health-driven status. → FE-01…11.

### Suggested target backend shape
```
api/            thin routes: auth dep, tenant dep, validation, error envelope
core/
  settings.py   pydantic-settings (env + optional YAML)
  security/     authn, authz (RBAC), rate limit, audit sink
llm/
  base.py       LLMProvider protocol
  providers/    gemini.py, openai_compatible.py, ...   (factory: get_llm_provider())
  prompts/      templated, overridable per deployment/tenant
db/
  dialects/     registry: prompt snippet + quoting + driver per dialect
  engines.py    pooled engines cached per (tenant, db_uri)
  guard.py      sqlglot allow-model: single SELECT, table/column allowlist, RLS injection, masking
governance/     tenant config, schema allowlist, semantic layer
services/       orchestration, threadpool offload, audit emit
graphs/agents/  the pipeline (unchanged backbone)
```

---

## 5. Appendix — audit provenance

- Raw structured result (all 57 findings incl. full adversarial verdicts): the workflow return in
  the session's `tasks/` output (189 KB JSON).
- Per-agent transcripts: `…/subagents/workflows/wf_1310024e-78f/journal.jsonl`.
- Every critical/high finding lists the exact `file:line` it was confirmed at; medium/low findings
  were reported by the dimension agents but not independently re-verified (lower confidence).
