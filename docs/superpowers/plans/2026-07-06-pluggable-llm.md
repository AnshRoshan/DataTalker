# Pluggable LLM Provider (EC-01) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardwired `backend/llm/gemini.py` with a provider seam so any deployment can run on Gemini OR any OpenAI-compatible endpoint (OpenAI, Azure, vLLM, Ollama, LiteLLM proxy) via env config alone.

**Architecture:** A tiny `LLMProvider` protocol (`complete(system, user) -> str`) with two thin HTTP adapters, a cached env-driven factory, and a `service.py` that owns prompts, the retry loop, and JSON parsing. The three agents swap one import each; the LangGraph wiring and all state keys are untouched because the two public functions keep identical return contracts.

**Tech Stack:** Python 3.13, `requests` (already installed), stdlib only. **No new dependencies.**

**Spec:** `docs/superpowers/specs/2026-07-06-pluggable-llm-design.md` (read it if anything here seems ambiguous — the spec wins).

## Global Constraints

- Branch: `phase2-pluggable-llm`. Work from repo root `E:\GENAI-PROJECTS\DataTalker`.
- **No new dependencies** — do not touch `pyproject.toml`, `requirements.txt`, or `uv.lock`.
- Tests are **assert-based plain-python files** in `backend/` (NOT pytest, NO fixtures) — match the existing `backend/test_*.py` style. Run with `uv run --directory backend python test_X.py`.
- Return contracts are FROZEN: `generate_sql_or_response` → `{"sql": str}` | `{"response": str}` | `{"error": str, "retryable": bool}`; `format_answer` → `{"answer": str, "follow_up_questions": list}` and **never** an error dict.
- Generic client-facing error text only (PR-05): transport failures become `"The language model is unavailable."`; full detail goes to `logging` at warning, never in the returned dict.
- Only touch stack ① files listed per task. Never edit `enterprise_*`, `core/{auth,security,middleware,monitoring,tasks,task_implementations}.py`, or top-level `main_graph.py`.
- Every commit message ends with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- Windows host: prefer the listed `uv run --directory backend python ...` commands verbatim; they work from repo root in both PowerShell and Git Bash.

---

### Task 1: Package scaffolding + `base.py` + `prompts.py`

**Files:**
- Create: `backend/llm/__init__.py` (empty — `api/` and `core/` have one; match)
- Create: `backend/llm/providers/__init__.py` (empty)
- Create: `backend/llm/base.py`
- Create: `backend/llm/prompts.py`

**Interfaces:**
- Consumes: nothing (leaf task).
- Produces (later tasks rely on these EXACT names):
  - `llm.base.LLMError(message: str, retryable: bool = True)` — exception with `.retryable` attr
  - `llm.base.LLMProvider` — Protocol with `complete(self, system: str, user: str) -> str`
  - `llm.prompts.build_sql_instruction(db_dialect: Literal["sqlite", "postgresql"] = "sqlite") -> str`
  - `llm.prompts.build_answer_instruction() -> str`

- [ ] **Step 1: Create the empty package markers**

Create `backend/llm/__init__.py` and `backend/llm/providers/__init__.py`, both containing exactly one line:

```python
```
(i.e. empty files — 0 bytes is fine.)

- [ ] **Step 2: Write `backend/llm/base.py`**

```python
# llm/base.py
"""The provider seam: one protocol + one exception.

Providers return raw model text; ALL prompt building, JSON parsing, and the
retry loop live in llm/service.py. Adapters stay tiny and share zero logic.
"""
from typing import Protocol


class LLMError(Exception):
    """Transport-level failure talking to a provider (network, HTTP status, bad envelope).

    retryable=False means the failure is structural (e.g. malformed response
    envelope) and the service layer should not re-attempt.
    """

    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class LLMProvider(Protocol):
    def complete(self, system: str, user: str) -> str:
        """Send one system+user turn, return the model's raw text. Raises LLMError."""
        ...
```

- [ ] **Step 3: Write `backend/llm/prompts.py`**

This is a MOVE of the two system-instruction strings out of `backend/llm/gemini.py`
(`_get_system_instruction_for_sql` and the inline string in `format_answer`), with two
deliberate fixes marked `# FIX:` below. Do NOT delete `llm/gemini.py` yet (Task 5 does).

```python
# llm/prompts.py
"""System-instruction builders, moved out of the old llm/gemini.py.

Provider-agnostic: these are plain strings handed to LLMProvider.complete().
Two deliberate changes vs. the old file (both because the SEC-01 validator now
rejects multi-statement SQL unconditionally, so telling the model to produce it
only wastes retries):
  1. The SQL prompt now demands exactly ONE read-only SELECT/WITH statement.
  2. The answer prompt no longer mentions "multiple queries".
"""
from typing import Literal


def build_sql_instruction(
    db_dialect: Literal["sqlite", "postgresql"] = "sqlite",
) -> str:
    """Generates the system instruction tailored to the specified SQL dialect."""
    dialect_specific_context = ""
    dialect_specific_practices = ""

    if db_dialect == "sqlite":
        dialect_specific_context = "You are working with SQLite databases."
        dialect_specific_practices = "- Ensure all SQL is valid SQLite syntax.\n"
    elif db_dialect == "postgresql":
        dialect_specific_context = "You are working with PostgreSQL databases."
        dialect_specific_practices = (
            "- Use standard SQL syntax compatible with PostgreSQL.\n"
            "- Pay attention to PostgreSQL-specific functions and data types where applicable.\n"
            "- Use double quotes for identifiers (table/column names) only when necessary (e.g., spaces or special characters), otherwise use standard unquoted names.\n"
            "- Use single quotes for string literals.\n"
            "- Ensure all SQL is valid PostgreSQL syntax.\n"
        )
    else:
        dialect_specific_context = (
            "You are working with a SQL database (defaulting to SQLite behavior)."
        )
        dialect_specific_practices = "- Ensure all SQL is valid SQLite syntax.\n"

    return (
        f"You are an expert SQL assistant for database queries. Your role is to analyze user questions and determine the appropriate response based on the database schema.\n\n"
        f"## TARGET DATABASE DIALECT: {db_dialect.upper()}\n\n"
        "## DECISION LOGIC:\n"
        "1. **SQL REQUIRED**: If the question asks about data in the database (counts, lookups, aggregations, trends, listings), generate SQL.\n"
        "2. **DIRECT RESPONSE**: If the question is conversational, about your capabilities, or cannot be answered from the schema, respond directly without SQL.\n\n"
        f"## DATABASE CONTEXT:\n{dialect_specific_context}\n"
        "Use ONLY the tables and columns present in the provided schema when generating SQL.\n\n"
        "## RESPONSE FORMATS:\n"
        'For SQL queries: Return ONLY a JSON object like: {"sql": "<your_optimized_sql_query>"}\n'
        'For direct answers: Return ONLY a JSON object like: {"response": "<your_natural_language_response>"}\n\n'
        f"## SQL BEST PRACTICES (General & {db_dialect.upper()} Specific):\n"
        "- Analyze the schema carefully before writing any query.\n"
        "- Use proper JOIN syntax for related tables (prefer INNER JOIN, LEFT JOIN etc. over implicit joins).\n"
        "- Include appropriate WHERE clauses for filtering.\n"
        "- Use aggregate functions (COUNT, SUM, AVG, MIN, MAX) where needed.\n"
        "- Order results logically (ORDER BY).\n"
        "- Limit results where appropriate (e.g., LIMIT 10), unless the user asks for all data.\n"
        "- Use table aliases for readability, especially in joins (e.g., SELECT c.name FROM customers c ...).\n"
        # FIX: was "Multiple statements can be separated by semicolons when needed."
        # — the SEC-01 validator rejects multi-statement SQL, so that advice
        # guaranteed rejected queries and wasted retries.
        "- Write exactly ONE read-only SELECT (or WITH ... SELECT) statement. Never use multiple statements, semicolons between statements, or any INSERT/UPDATE/DELETE/DDL.\n"
        "- Ensure column names and table names exactly match the provided schema.\n"
        f"{dialect_specific_practices}"
        "## TABLE INFORMATION GUIDELINES:\n"
        "When schema is provided, analyze:\n"
        "- Table names and purposes\n"
        "- Column names and data types\n"
        "- Primary and foreign key relationships\n"
        "- Row counts (if provided) for context\n"
        "- Potential data patterns\n\n"
        "CRITICAL: Return ONLY valid JSON as specified in RESPONSE FORMATS. No markdown, explanations, comments, or any other text outside the JSON structure."
    )


def build_answer_instruction() -> str:
    """System instruction for formatting query results into a natural-language answer."""
    return (
        "You are an expert data analyst who formats database query results into clear, human-readable responses.\n\n"
        "## YOUR ROLE:\n"
        "Transform raw database results into meaningful, well-structured answers that directly address the user's question.\n\n"
        "## FORMATTING GUIDELINES:\n"
        "1. **Direct Answers**: Start with a clear, direct response to the question\n"
        "2. **Data Presentation**: Present data in a logical, easy-to-read format\n"
        "3. **Context**: Provide relevant context or insights when appropriate\n"
        "4. **Numbers**: Format numbers clearly (use commas for thousands, appropriate decimal places)\n"
        "5. **Tables**: When multiple records are returned, suggest a tabular format for frontend display\n\n"
        # FIX: dropped guideline 6 ("Multiple Queries") and its example below —
        # SEC-01 made multi-statement results impossible.
        "## RESPONSE FORMAT:\n"
        "Return a JSON object with the following structure:\n"
        "{\n"
        '  "answer": "<main answer to the question>",\n'
        '  "follow_up_questions": ["<question1>", "<question2>", ...]\n'
        "}\n\n"
        "## FOLLOW-UP QUESTION GUIDELINES:\n"
        "Generate follow-up questions when:\n"
        "- The results suggest natural next questions about the data\n"
        "- The user might want to drill into or aggregate the data differently\n"
        "- Related tables in the schema could enrich the answer\n"
        "- The response could lead to practical database exploration\n\n"
        "Make follow-up questions specific to the actual context. If no relevant follow-up questions exist, use an empty array [].\n\n"
        "## EXAMPLES:\n"
        '- For counts: {"answer": "There are 25 users in the database.", "follow_up_questions": []}\n'
        '- For trends: {"answer": "Sales increased 15% this quarter.", "follow_up_questions": ["Which products drove the sales increase?", "How does this compare to last year?"]}\n'
        '- For direct responses: {"answer": "I am an AI assistant for database queries.", "follow_up_questions": ["What tables are available in this database?", "Show me some sample data"]}\n\n'
        "CRITICAL: Return ONLY valid JSON. No markdown, explanations, or formatting."
    )
```

- [ ] **Step 4: Smoke-check the builders**

Run:
```bash
uv run --directory backend python -c "from llm.prompts import build_sql_instruction, build_answer_instruction; s = build_sql_instruction('postgresql'); assert 'POSTGRESQL' in s; assert 'Multiple statements' not in s; assert 'exactly ONE read-only SELECT' in s; a = build_answer_instruction(); assert 'follow_up_questions' in a; assert 'Multiple Queries' not in a; from llm.base import LLMError; e = LLMError('x', retryable=False); assert e.retryable is False; print('task1 ok')"
```
Expected: `task1 ok`

- [ ] **Step 5: Commit**

```bash
git add backend/llm/__init__.py backend/llm/providers/__init__.py backend/llm/base.py backend/llm/prompts.py
git commit -m "LLM seam scaffolding: LLMProvider protocol + provider-agnostic prompts (EC-01)

Prompts moved out of llm/gemini.py with two fixes: the SQL prompt now demands
a single read-only SELECT (the old multi-statement advice guaranteed SEC-01
validator rejections), and the answer prompt drops multi-query guidance.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: The two provider adapters (TDD)

**Files:**
- Create: `backend/llm/providers/gemini.py`
- Create: `backend/llm/providers/openai_compat.py`
- Test: `backend/test_llm_providers.py`

**Interfaces:**
- Consumes: `llm.base.LLMError` (from Task 1).
- Produces (Task 3 and 4 rely on these EXACT constructors):
  - `llm.providers.gemini.GeminiProvider(api_key: str, model: str, temperature: float | None = None)` with `complete(system, user) -> str`
  - `llm.providers.openai_compat.OpenAICompatProvider(api_key: str, base_url: str, model: str, temperature: float | None = None)` with `complete(system, user) -> str`

**Error-mapping rules (both providers):** network exception → `LLMError(retryable=True)`; non-200 status → `LLMError(retryable=True)` with status + first 500 chars of body in the message (this goes to LOGS only, service layer genericizes for clients); response JSON missing the expected envelope keys → `LLMError(retryable=False)`.

- [ ] **Step 1: Write the failing test `backend/test_llm_providers.py`**

```python
# backend/test_llm_providers.py
# Assert-based self-check for the two LLM provider adapters (no network: requests is stubbed).
#   uv run --directory backend python test_llm_providers.py
import json

from llm.base import LLMError
import llm.providers.gemini as gemini_mod
import llm.providers.openai_compat as openai_mod
from llm.providers.gemini import GeminiProvider
from llm.providers.openai_compat import OpenAICompatProvider


class _Resp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class _FakeRequests:
    """Stands in for the `requests` module inside a provider module."""

    exceptions = __import__("requests").exceptions  # real exception types

    def __init__(self, resp=None, raise_exc=None):
        self.resp = resp
        self.raise_exc = raise_exc
        self.captured = None  # (url, kwargs)

    def post(self, url, **kwargs):
        self.captured = (url, kwargs)
        if self.raise_exc:
            raise self.raise_exc
        return self.resp


def expect_llm_error(fn, retryable):
    try:
        fn()
    except LLMError as e:
        assert e.retryable is retryable, f"retryable={e.retryable}, want {retryable}"
        return
    raise AssertionError("expected LLMError")


# ---------- GeminiProvider ----------
ok_gemini = _Resp(200, {"candidates": [{"content": {"parts": [{"text": "  hello  "}]}}]})
fake = _FakeRequests(ok_gemini)
gemini_mod.requests = fake
p = GeminiProvider(api_key="gk", model="gemini-1.5-flash", temperature=None)
assert p.complete("SYS", "USR") == "hello"
url, kw = fake.captured
assert "models/gemini-1.5-flash:generateContent" in url
assert kw["headers"]["x-goog-api-key"] == "gk"                       # key in header (PR-05), never in URL
assert "key=" not in url
assert kw["json"]["contents"][0]["parts"][0]["text"] == "SYS\n\nUSR"  # system prompt inlined, same as pre-refactor
assert "generationConfig" not in kw["json"]                           # temperature unset -> omitted
assert kw["timeout"] == 60

# temperature set -> generationConfig sent
fake = _FakeRequests(ok_gemini)
gemini_mod.requests = fake
GeminiProvider(api_key="gk", model="m", temperature=0.2).complete("s", "u")
assert fake.captured[1]["json"]["generationConfig"] == {"temperature": 0.2}

# non-200 -> retryable LLMError
gemini_mod.requests = _FakeRequests(_Resp(500, {"error": "boom"}))
expect_llm_error(lambda: p.complete("s", "u"), retryable=True)

# bad envelope -> NON-retryable LLMError
gemini_mod.requests = _FakeRequests(_Resp(200, {"unexpected": "shape"}))
expect_llm_error(lambda: p.complete("s", "u"), retryable=False)

# network exception -> retryable LLMError
gemini_mod.requests = _FakeRequests(raise_exc=_FakeRequests.exceptions.ConnectionError("down"))
expect_llm_error(lambda: p.complete("s", "u"), retryable=True)

# ---------- OpenAICompatProvider ----------
ok_openai = _Resp(200, {"choices": [{"message": {"content": " hi there "}}]})
fake = _FakeRequests(ok_openai)
openai_mod.requests = fake
q = OpenAICompatProvider(api_key="ok1", base_url="http://localhost:8001/v1/", model="llama-3", temperature=None)
assert q.complete("SYS", "USR") == "hi there"
url, kw = fake.captured
assert url == "http://localhost:8001/v1/chat/completions"            # trailing slash on base_url handled
assert kw["headers"]["Authorization"] == "Bearer ok1"
assert kw["json"]["model"] == "llama-3"
assert kw["json"]["messages"] == [
    {"role": "system", "content": "SYS"},
    {"role": "user", "content": "USR"},
]
assert "temperature" not in kw["json"]
assert kw["timeout"] == 60

# temperature set -> included
fake = _FakeRequests(ok_openai)
openai_mod.requests = fake
OpenAICompatProvider(api_key="k", base_url="http://x/v1", model="m", temperature=0.5).complete("s", "u")
assert fake.captured[1]["json"]["temperature"] == 0.5

# non-200 -> retryable; bad envelope (content=None, e.g. tool-call reply) -> non-retryable
openai_mod.requests = _FakeRequests(_Resp(429, {"error": "rate limited"}))
expect_llm_error(lambda: q.complete("s", "u"), retryable=True)
openai_mod.requests = _FakeRequests(_Resp(200, {"choices": [{"message": {"content": None}}]}))
expect_llm_error(lambda: q.complete("s", "u"), retryable=False)
openai_mod.requests = _FakeRequests(raise_exc=_FakeRequests.exceptions.Timeout("slow"))
expect_llm_error(lambda: q.complete("s", "u"), retryable=True)

print("llm_providers: all assertions passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python test_llm_providers.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'llm.providers.gemini'`

- [ ] **Step 3: Write `backend/llm/providers/gemini.py`**

```python
# llm/providers/gemini.py
"""Google Gemini via the public generateContent REST API (no SDK, matches pre-refactor)."""
import requests

from llm.base import LLMError

_TIMEOUT_SECONDS = 60


class GeminiProvider:
    def __init__(self, api_key: str, model: str, temperature: float | None = None):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature

    def complete(self, system: str, user: str) -> str:
        # Gemini has a dedicated systemInstruction field, but the pre-refactor code
        # inlined the system prompt into the single user turn; keep that behavior.
        payload = {
            "contents": [{"role": "user", "parts": [{"text": f"{system}\n\n{user}"}]}]
        }
        if self.temperature is not None:
            payload["generationConfig"] = {"temperature": self.temperature}
        try:
            response = requests.post(
                url=f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": self.api_key,  # header, never URL param (PR-05)
                },
                json=payload,
                timeout=_TIMEOUT_SECONDS,
            )
        except requests.exceptions.RequestException as e:
            raise LLMError(f"Network error calling Gemini: {e}") from e
        if response.status_code != 200:
            raise LLMError(f"Gemini API error {response.status_code}: {response.text[:500]}")
        try:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as e:
            raise LLMError(f"Unexpected Gemini response structure: {e}", retryable=False) from e
```

- [ ] **Step 4: Write `backend/llm/providers/openai_compat.py`**

```python
# llm/providers/openai_compat.py
"""Any /chat/completions-compatible endpoint: OpenAI, Azure, vLLM, Ollama, LiteLLM proxy."""
import requests

from llm.base import LLMError

_TIMEOUT_SECONDS = 60


class OpenAICompatProvider:
    def __init__(self, api_key: str, base_url: str, model: str, temperature: float | None = None):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature

    def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        try:
            response = requests.post(
                url=f"{self.base_url}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                json=payload,
                timeout=_TIMEOUT_SECONDS,
            )
        except requests.exceptions.RequestException as e:
            raise LLMError(f"Network error calling LLM endpoint: {e}") from e
        if response.status_code != 200:
            raise LLMError(f"LLM API error {response.status_code}: {response.text[:500]}")
        try:
            return response.json()["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as e:
            # AttributeError covers content=None (e.g. a tool-call-only reply)
            raise LLMError(f"Unexpected LLM response structure: {e}", retryable=False) from e
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --directory backend python test_llm_providers.py`
Expected: `llm_providers: all assertions passed`

- [ ] **Step 6: Commit**

```bash
git add backend/llm/providers/gemini.py backend/llm/providers/openai_compat.py backend/test_llm_providers.py
git commit -m "Add GeminiProvider + OpenAICompatProvider adapters (EC-01)

Thin HTTP adapters behind the LLMProvider protocol. Error mapping: network/
non-200 -> retryable LLMError; bad response envelope -> non-retryable. Keys
travel in headers only. No SDKs, no new dependencies.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: The factory (TDD)

**Files:**
- Create: `backend/llm/factory.py`
- Test: `backend/test_llm_factory.py`

**Interfaces:**
- Consumes: `GeminiProvider`, `OpenAICompatProvider` (Task 2 constructors, exact signatures above).
- Produces (Task 4 relies on this): `llm.factory.get_provider() -> LLMProvider` — cached via `functools.lru_cache(maxsize=1)` so `.cache_clear()` exists for tests.

**Selection rules (from the spec):** `LLM_PROVIDER` unset/`gemini` → `GeminiProvider` (requires `GEMINI_API_KEY`; `LLM_MODEL` defaults to `gemini-1.5-flash`); `openai` → `OpenAICompatProvider` (requires `LLM_API_KEY`, `LLM_BASE_URL`, **and** `LLM_MODEL`); anything else → `RuntimeError` naming the bad value. Missing var → `RuntimeError` naming the exact var. `LLM_TEMPERATURE` unset → `None` (provider omits it).

- [ ] **Step 1: Write the failing test `backend/test_llm_factory.py`**

```python
# backend/test_llm_factory.py
# Assert-based self-check for env-driven provider selection (EC-01).
#   uv run --directory backend python test_llm_factory.py
import os

from llm.factory import get_provider
from llm.providers.gemini import GeminiProvider
from llm.providers.openai_compat import OpenAICompatProvider


def reset(**env):
    """Set exactly the LLM env we want, clear the factory cache."""
    for var in ("LLM_PROVIDER", "LLM_MODEL", "LLM_TEMPERATURE", "GEMINI_API_KEY", "LLM_API_KEY", "LLM_BASE_URL"):
        os.environ.pop(var, None)
    os.environ.update(env)
    get_provider.cache_clear()


def expect_error(naming):
    try:
        get_provider()
    except RuntimeError as e:
        assert naming in str(e), f"error should name {naming!r}, got: {e}"
        return
    raise AssertionError(f"expected RuntimeError naming {naming!r}")


# default (LLM_PROVIDER unset) -> Gemini with the default model
reset(GEMINI_API_KEY="g")
p = get_provider()
assert isinstance(p, GeminiProvider)
assert p.model == "gemini-1.5-flash"
assert p.temperature is None

# explicit gemini + custom model + temperature
reset(LLM_PROVIDER="gemini", GEMINI_API_KEY="g", LLM_MODEL="gemini-2.0-flash", LLM_TEMPERATURE="0.3")
p = get_provider()
assert isinstance(p, GeminiProvider) and p.model == "gemini-2.0-flash" and p.temperature == 0.3

# the cache is real: same object until cache_clear
assert get_provider() is p

# openai happy path (trailing slash normalized by the provider itself)
reset(LLM_PROVIDER="openai", LLM_API_KEY="k", LLM_BASE_URL="http://localhost:8001/v1", LLM_MODEL="llama-3")
q = get_provider()
assert isinstance(q, OpenAICompatProvider) and q.model == "llama-3" and q.base_url == "http://localhost:8001/v1"

# missing required config -> RuntimeError naming the exact var
reset(LLM_PROVIDER="openai", LLM_API_KEY="k", LLM_MODEL="m")
expect_error("LLM_BASE_URL")
reset(LLM_PROVIDER="openai", LLM_BASE_URL="http://x/v1", LLM_MODEL="m")
expect_error("LLM_API_KEY")
reset(LLM_PROVIDER="openai", LLM_API_KEY="k", LLM_BASE_URL="http://x/v1")
expect_error("LLM_MODEL")
reset()  # gemini default, no key
expect_error("GEMINI_API_KEY")

# unknown provider name -> named in the error
reset(LLM_PROVIDER="banana", GEMINI_API_KEY="g")
expect_error("banana")

print("llm_factory: all assertions passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python test_llm_factory.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'llm.factory'`

- [ ] **Step 3: Write `backend/llm/factory.py`**

```python
# llm/factory.py
"""Env-driven provider selection. Read once, cached; misconfig raises a clear
error at FIRST USE (not import), naming the exact missing variable."""
import os
from functools import lru_cache

from dotenv import load_dotenv

from llm.base import LLMProvider
from llm.providers.gemini import GeminiProvider
from llm.providers.openai_compat import OpenAICompatProvider

load_dotenv()  # same pattern as the old llm/gemini.py: honor backend/.env

_DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"


def _require(var: str, provider: str) -> str:
    value = os.getenv(var)
    if not value:
        raise RuntimeError(f"{var} is required for the '{provider}' LLM provider.")
    return value


@lru_cache(maxsize=1)
def get_provider() -> LLMProvider:
    name = (os.getenv("LLM_PROVIDER") or "gemini").strip().lower()
    raw_temp = os.getenv("LLM_TEMPERATURE")
    temperature = float(raw_temp) if raw_temp else None  # unset -> provider default
    if name == "gemini":
        return GeminiProvider(
            api_key=_require("GEMINI_API_KEY", name),
            model=os.getenv("LLM_MODEL") or _DEFAULT_GEMINI_MODEL,
            temperature=temperature,
        )
    if name == "openai":
        return OpenAICompatProvider(
            api_key=_require("LLM_API_KEY", name),
            base_url=_require("LLM_BASE_URL", name),
            model=_require("LLM_MODEL", name),  # a BYO endpoint has no sane default model
            temperature=temperature,
        )
    raise RuntimeError(f"Unknown LLM_PROVIDER '{name}' (expected 'gemini' or 'openai').")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory backend python test_llm_factory.py`
Expected: `llm_factory: all assertions passed`

(Note: `load_dotenv()` never overrides variables the test already set/popped in `os.environ`? It DOES populate ones that are absent — that's why `reset()` runs `pop` + `update` **after** import time and then clears the cache. If `expect_error("GEMINI_API_KEY")` fails because your real `backend/.env` key leaked in, the cause is that `reset()` didn't pop — check the pop list.)

- [ ] **Step 5: Commit**

```bash
git add backend/llm/factory.py backend/test_llm_factory.py
git commit -m "Add env-driven LLM provider factory (EC-01)

LLM_PROVIDER=gemini (default) | openai. Cached singleton; missing config
raises a clear error naming the exact variable at first use, not import.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: The service layer (TDD) — retry loop + parsing, contracts frozen

**Files:**
- Create: `backend/llm/service.py`
- Test: `backend/test_llm_service.py`

**Interfaces:**
- Consumes: `llm.factory.get_provider()`, `llm.base.LLMError`, `llm.prompts.build_sql_instruction` / `build_answer_instruction`.
- Produces (Task 5's agents call these EXACT names):
  - `llm.service.generate_sql_or_response(schema: str, question: str, db_dialect: Literal["sqlite","postgresql"] = "sqlite") -> dict` — returns `{"sql": str, "retryable": False}` | `{"response": str, "retryable": False}` | `{"error": str, "retryable": bool, ...}`
  - `llm.service.format_answer(question, result) -> dict` — ALWAYS `{"answer": str, "follow_up_questions": list}`, never an error dict
  - Module-level `MAX_RETRIES = 3` and `RETRY_DELAY_SECONDS = 2` (tests patch the latter to 0)

**Why the retry loop is HERE and not in providers:** the old Gemini loop retried *parse* failures (model returned non-JSON) as well as transport errors — and parsing only happens at this layer. `SQLRetryAgent` in the graph does NOT cover this (it only retries empty results after successful execution). See the spec.

- [ ] **Step 1: Write the failing test `backend/test_llm_service.py`**

```python
# backend/test_llm_service.py
# Assert-based self-check for the provider-agnostic LLM service (EC-01).
# Uses a FakeProvider — no network, no API keys needed.
#   uv run --directory backend python test_llm_service.py
from llm.base import LLMError
import llm.service as svc

svc.RETRY_DELAY_SECONDS = 0  # keep retries instant in tests


class FakeProvider:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0
        self.seen = []  # (system, user) per call

    def complete(self, system, user):
        self.calls += 1
        self.seen.append((system, user))
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def with_fake(*outputs):
    fake = FakeProvider(outputs)
    svc.get_provider = lambda: fake  # service looked it up via `from llm.factory import get_provider`
    return fake


# --- generate_sql_or_response: the three contract shapes ---
with_fake('{"sql": "SELECT 1"}')
r = svc.generate_sql_or_response("schema here", "how many?")
assert r["sql"] == "SELECT 1" and "error" not in r

with_fake('{"response": "I can only answer data questions."}')
r = svc.generate_sql_or_response("s", "hi")
assert r["response"] == "I can only answer data questions."

# markdown fences stripped (the old \\s regex bug is fixed; behavior identical)
with_fake('```json\n{"sql": "SELECT 2"}\n```')
assert svc.generate_sql_or_response("s", "q")["sql"] == "SELECT 2"

# --- THE key behavior this refactor must not lose: parse-failure retry ---
fake = with_fake("total garbage, not json", '{"sql": "SELECT 3"}')
r = svc.generate_sql_or_response("s", "q")
assert r["sql"] == "SELECT 3", r
assert fake.calls == 2, "bad JSON must trigger a retry, not an immediate error"

# always-garbage -> error after MAX_RETRIES attempts
fake = with_fake("junk", "junk", "junk")
r = svc.generate_sql_or_response("s", "q")
assert "error" in r and r["retryable"] is True
assert fake.calls == svc.MAX_RETRIES

# empty sql / wrong keys -> retryable error dict (not a crash)
fake = with_fake('{"sql": ""}', '{"wrong": 1}', '[1, 2]')
r = svc.generate_sql_or_response("s", "q")
assert "error" in r and fake.calls == svc.MAX_RETRIES

# --- transport failures ---
fake = with_fake(LLMError("boom"), LLMError("boom"), LLMError("boom"))
r = svc.generate_sql_or_response("s", "q")
assert r["error"] == "The language model is unavailable."  # generic, PR-05
assert r["retryable"] is True and fake.calls == 3

fake = with_fake(LLMError("bad envelope", retryable=False))
r = svc.generate_sql_or_response("s", "q")
assert "error" in r and fake.calls == 1, "non-retryable transport error must not be retried"

# transport error then success -> recovered
fake = with_fake(LLMError("blip"), '{"sql": "SELECT 4"}')
assert svc.generate_sql_or_response("s", "q")["sql"] == "SELECT 4" and fake.calls == 2

# --- prompts actually reach the model, with the single-statement rule ---
fake = with_fake('{"sql": "SELECT 1"}')
svc.generate_sql_or_response("THE_SCHEMA", "THE_QUESTION", db_dialect="postgresql")
system_sent, user_sent = fake.seen[0]
assert "POSTGRESQL" in system_sent
assert "exactly ONE read-only SELECT" in system_sent
assert "Multiple statements" not in system_sent
assert "THE_SCHEMA" in user_sent and "THE_QUESTION" in user_sent

# --- format_answer: contract is ALWAYS {"answer", "follow_up_questions"} ---
with_fake('{"answer": "There are 42 patients.", "follow_up_questions": ["By ward?"]}')
r = svc.format_answer("how many patients?", [{"count": 42}])
assert r == {"answer": "There are 42 patients.", "follow_up_questions": ["By ward?"]}

# fenced JSON handled
with_fake('```json\n{"answer": "ok", "follow_up_questions": []}\n```')
assert svc.format_answer("q", [])["answer"] == "ok"

# non-JSON -> raw text becomes the answer (pre-refactor fallback), single attempt
fake = with_fake("Just a plain sentence.")
r = svc.format_answer("q", [])
assert r == {"answer": "Just a plain sentence.", "follow_up_questions": []}
assert fake.calls == 1

# transport failure -> generic apology, never an {"error"} dict
fake = with_fake(LLMError("x"), LLMError("x"), LLMError("x"))
r = svc.format_answer("q", [])
assert "error" not in r and "answer" in r and r["follow_up_questions"] == []

# --- provider misconfig (factory RuntimeError) -> clean NON-retryable error, no retry ---
# Spec: "Missing required config raises a clear error ... not a vague 500."
calls = {"n": 0}
def boom():
    calls["n"] += 1
    raise RuntimeError("LLM_BASE_URL is required for the 'openai' LLM provider.")
svc.get_provider = boom
r = svc.generate_sql_or_response("s", "q")
assert "LLM_BASE_URL" in r["error"] and r["retryable"] is False and calls["n"] == 1

print("llm_service: all assertions passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python test_llm_service.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'llm.service'`

- [ ] **Step 3: Write `backend/llm/service.py`**

```python
# llm/service.py
"""Provider-agnostic LLM service: the two functions the agents call.

Contracts (unchanged from the old llm/gemini.py — the agents and graph depend on them):
- generate_sql_or_response -> {"sql": str} | {"response": str} | {"error": str, "retryable": bool}
- format_answer            -> {"answer": str, "follow_up_questions": list}   (never an error dict)

The retry loop lives HERE, not in providers, because it must also cover parse
failures (the model returning non-JSON) — which only this layer can detect.
SQLRetryAgent in the graph only retries empty results after execution.
"""
import json
import logging
import re
import time
from typing import Any, Callable, Dict, Literal

from llm.base import LLMError
from llm.factory import get_provider
from llm.prompts import build_answer_instruction, build_sql_instruction

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2

_GENERIC_UNAVAILABLE = "The language model is unavailable."


def _strip_fences(text: str) -> str:
    """Remove a surrounding ```/```json markdown fence, if present."""
    content = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    return re.sub(r"\s*```$", "", content)


def _parse_sql_response(response_text: str) -> Dict[str, Any]:
    """Moved from llm/gemini.py:_parse_and_validate_gemini_response — contract unchanged.

    (The old fence-stripping regex used r"\\s*" — a literal backslash — and never
    matched; the re.search fallback made it work anyway. _strip_fences fixes the
    regex; the fallback is kept for JSON embedded in prose.)
    """
    if not response_text:
        return {"error": "LLM returned an empty response.", "retryable": True}
    content = _strip_fences(response_text)
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            return {"error": "LLM did not return valid JSON.", "retryable": True, "raw_content": response_text}
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {"error": "LLM returned malformed JSON.", "retryable": True, "raw_content": response_text}
    if not isinstance(parsed, dict):
        return {
            "error": f"LLM JSON was not an object (got {type(parsed).__name__}).",
            "retryable": True,
            "raw_content": content,
        }
    sql = parsed.get("sql")
    if isinstance(sql, str) and sql.strip():
        if "SELECT _FROM" in sql:  # known bad-generation pattern, kept from the old parser
            return {"error": "LLM generated potentially invalid SQL.", "retryable": True, "raw_content": content}
        return {"sql": sql, "retryable": False}
    response = parsed.get("response")
    if isinstance(response, str) and response.strip():
        return {"response": response, "retryable": False}
    return {
        "error": f"LLM JSON missing a non-empty 'sql' or 'response' key. Found keys: {list(parsed.keys())}",
        "retryable": True,
        "raw_content": content,
    }


def _parse_answer(response_text: str) -> Dict[str, Any]:
    """Answer formatting is best-effort: non-JSON output falls back to the raw text
    as the answer (pre-refactor behavior) instead of triggering a retry."""
    content = _strip_fences(response_text)
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("Answer formatter returned non-JSON; falling back to raw text.")
        return {"answer": content, "follow_up_questions": []}
    if not isinstance(parsed, dict):
        return {"answer": content, "follow_up_questions": []}
    return {
        "answer": parsed.get("answer", "Could not format the results."),
        "follow_up_questions": parsed.get("follow_up_questions", []),
    }


def _complete_with_retries(
    system: str, user: str, parse: Callable[[str], Dict[str, Any]]
) -> Dict[str, Any]:
    """Call the provider, parse its text; retry (with backoff) on retryable failures."""
    last_error: Dict[str, Any] = {"error": _GENERIC_UNAVAILABLE, "retryable": True}
    for attempt in range(MAX_RETRIES):
        try:
            text = get_provider().complete(system, user)
        except LLMError as e:
            # Full detail to logs only; clients get a generic message (PR-05).
            logger.warning("LLM transport failure (attempt %d/%d): %s", attempt + 1, MAX_RETRIES, e)
            last_error = {"error": _GENERIC_UNAVAILABLE, "retryable": e.retryable}
            if not e.retryable:
                return last_error
            time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
            continue
        except RuntimeError as e:
            # Provider misconfig from the factory (names an env var, no secrets).
            # Spec: a clear error at first use, never a vague 500. Never retryable.
            logger.warning("LLM provider misconfigured: %s", e)
            return {"error": str(e), "retryable": False}
        parsed = parse(text)
        if "error" not in parsed:
            return parsed
        last_error = parsed
        if not parsed.get("retryable"):
            return parsed
        logger.warning("LLM output rejected (attempt %d/%d): %s", attempt + 1, MAX_RETRIES, parsed.get("error"))
        time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
    logger.warning("All %d LLM attempts failed: %s", MAX_RETRIES, last_error.get("error"))
    return last_error


def generate_sql_or_response(
    schema: str, question: str, db_dialect: Literal["sqlite", "postgresql"] = "sqlite"
) -> Dict[str, Any]:
    """NL question + schema -> {"sql"} | {"response"} | {"error", "retryable"}."""
    system = build_sql_instruction(db_dialect)
    user = f"Schema:\n```\n{schema}\n```\n\nQuestion: {question}"
    return _complete_with_retries(system, user, _parse_sql_response)


def format_answer(question: Any, result: Any) -> Dict[str, Any]:
    """Query results -> {"answer", "follow_up_questions"}. Never returns an error dict."""
    system = build_answer_instruction()
    user = (
        f"Original Question: {question}\n\n"
        f"Query Results: {result}\n\n"
        "Task: Format the results into a structured JSON response with the main answer and relevant follow-up questions."
    )
    parsed = _complete_with_retries(system, user, _parse_answer)
    if "error" in parsed:
        return {"answer": "Sorry, I couldn't format the answer right now.", "follow_up_questions": []}
    return parsed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory backend python test_llm_service.py`
Expected: `llm_service: all assertions passed`

- [ ] **Step 5: Re-run the other new suites (regression)**

Run: `uv run --directory backend python test_llm_providers.py && uv run --directory backend python test_llm_factory.py`
Expected: both print `... all assertions passed`

- [ ] **Step 6: Commit**

```bash
git add backend/llm/service.py backend/test_llm_service.py
git commit -m "Add provider-agnostic LLM service: retry loop + parsing (EC-01)

Same two public contracts as the old llm/gemini.py. The MAX_RETRIES loop
wraps complete()+parse so bad-JSON model output is still retried (the old
behavior SQLRetryAgent does not cover). Transport failures return a generic
message; detail goes to logs (PR-05). Fixes the latent \\\\s fence-regex bug.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Rewire the three agents, delete `llm/gemini.py`

**Files:**
- Modify: `backend/agents/sql_writer.py:2,37`
- Modify: `backend/agents/sql_retry.py:2,45,111,117`
- Modify: `backend/agents/answer.py:2`
- Delete: `backend/llm/gemini.py`

**Interfaces:**
- Consumes: `llm.service.generate_sql_or_response(schema=..., question=..., db_dialect=...)` and `llm.service.format_answer(question, result)` (Task 4). Same kwargs, same return dicts — the bodies of the agents need NO logic changes beyond the two deletions below.

- [ ] **Step 1: `agents/sql_writer.py` — swap the import and call**

Line 2, old:
```python
from llm.gemini import generate_sql_or_response_with_gemini
```
new:
```python
from llm.service import generate_sql_or_response
```

Line ~37, old:
```python
        llm_result = generate_sql_or_response_with_gemini(
            schema=schema_description, question=question, db_dialect=db_dialect
        )
```
new:
```python
        llm_result = generate_sql_or_response(
            schema=schema_description, question=question, db_dialect=db_dialect
        )
```

- [ ] **Step 2: `agents/sql_retry.py` — same swap + remove the multi-query suggestions**

Line 2, old:
```python
from llm.gemini import generate_sql_or_response_with_gemini
```
new:
```python
from llm.service import generate_sql_or_response
```

Line ~45, old:
```python
        llm_result = generate_sql_or_response_with_gemini(
            schema=enhanced_schema, question=question, db_dialect=db_dialect
        )
```
new:
```python
        llm_result = generate_sql_or_response(
            schema=enhanced_schema, question=question, db_dialect=db_dialect
        )
```

In `_analyze_failure`, DELETE these two lines (they tell the model to emit multi-statement
SQL, which the SEC-01 validator rejects unconditionally — every such retry is a guaranteed
failure):

```python
        failure_analysis += "8. Generate multiple queries to explore available data first\n"
```
and
```python
            failure_analysis += "- Or combine: SELECT name FROM departments; SELECT * FROM appointments LIMIT 10;\n"
```
(Do not renumber items 1–7; item 8 was the last in its list.)

- [ ] **Step 3: `agents/answer.py` — swap the import**

Line 2, old:
```python
from llm.gemini import format_answer
```
new:
```python
from llm.service import format_answer
```
(The call site `format_answer(question, context_for_formatter)` is unchanged.)

- [ ] **Step 4: Delete the old module and verify nothing references it**

```bash
git rm backend/llm/gemini.py
```
Then run: `grep -rn "llm.gemini\|_with_gemini" backend --include="*.py"`
Expected: **no output** (exit code 1 is the success case for grep here).

- [ ] **Step 5: Verify the live app still imports and the whole suite is green**

Run (note: `main` imports the graph → agents → llm.service; this catches any wiring typo):
```bash
uv run --directory backend python -c "import os; os.environ.setdefault('GEMINI_API_KEY','dummy'); os.environ.setdefault('DATATALKER_API_KEY','k'); import main; print('app imports ok')"
```
Expected: `app imports ok`

Then the full suite:
```bash
uv run --directory backend python test_sql_guard.py
uv run --directory backend python test_executor.py
uv run --directory backend python test_auth.py
uv run --directory backend python test_input_guard.py
uv run --directory backend python test_schema_cache.py
uv run --directory backend python test_logging.py
uv run --directory backend python test_llm_providers.py
uv run --directory backend python test_llm_factory.py
uv run --directory backend python test_llm_service.py
```
Expected: every file prints `...: all assertions passed` (test_logging prints `logging: all assertions passed`).

- [ ] **Step 6: Commit**

```bash
git add backend/agents/sql_writer.py backend/agents/sql_retry.py backend/agents/answer.py
git commit -m "Rewire agents to llm.service; delete llm/gemini.py (EC-01 done)

Three import swaps, zero logic changes to the graph or state. Also removed
SQLRetryAgent's multi-query retry suggestions - the SEC-01 validator rejects
multi-statement SQL unconditionally, so they guaranteed failed retries.
No agent imports a concrete provider anymore.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
(The `git rm` from Step 4 is already staged; `git add` of the three agents completes the commit.)

---

### Task 6: Config docs — `.env.example`, CLAUDE.md, audit

**Files:**
- Modify: `backend/.env.example`
- Modify: `CLAUDE.md` (repo root)
- Modify: `docs/CODEBASE_AUDIT.md` (EC-01 entry only)

- [ ] **Step 1: Replace `backend/.env.example` with**

(While here: drop `GEMINI_API_URL`, `DEFAULT_DB_PATH`, `MAX_QUERY_RESULTS`, `DEBUG_MODE` — nothing in the code reads them; documenting fake knobs is doc/reality drift.)

```bash
# TalkToData Environment Configuration
# Copy this file to .env and fill in your actual values

# --- Required ---

# Gemini AI API Key — required when LLM_PROVIDER is unset or 'gemini'.
# Get one from: https://aistudio.google.com/apikey
GEMINI_API_KEY=your_gemini_api_key_here

# API auth key (Required) — clients must send `Authorization: Bearer <this>`.
# Data routes deny all requests until this is set. Use a long random value.
DATATALKER_API_KEY=change_me_to_a_long_random_secret

# --- LLM provider (EC-01: bring your own model) ---
# LLM_PROVIDER=gemini              # gemini (default) | openai
# LLM_MODEL=gemini-1.5-flash       # default for gemini; REQUIRED for openai
# LLM_TEMPERATURE=                 # unset -> provider default
# LLM_API_KEY=                     # required for openai
# LLM_BASE_URL=                    # required for openai. Examples:
#   OpenAI:        https://api.openai.com/v1
#   Ollama:        http://localhost:11434/v1
#   vLLM:          http://localhost:8001/v1
#   LiteLLM proxy: http://localhost:4000

# --- Optional ---
# DATATALKER_DB_DIR=               # db_path confinement dir (default: backend/)
# CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
# LOG_LEVEL=INFO
```

- [ ] **Step 2: Update `CLAUDE.md`** — exactly these spots:

1. Repo-layout block: replace the line
   ```
     llm/gemini.py           ① the ONLY LLM integration — hardcoded to Gemini over HTTPS
   ```
   with
   ```
     llm/                    ① pluggable LLM layer (EC-01): base.py protocol, providers/
                               (gemini, openai_compat), factory.py (env-driven), prompts.py,
                               service.py (the 2 funcs agents call; retry loop lives here)
   ```
2. In "Still open (Phase 2+)": remove the line `**EC-01 (next up):** LLM still hardwired to Gemini — no provider abstraction. The BYO-LLM wedge.` and add under the "Fixed" list:
   ```
   8. ✅ **EC-01** — pluggable LLM provider: `LLM_PROVIDER=gemini|openai` + `LLM_BASE_URL`
      runs any OpenAI-compatible endpoint (OpenAI/Azure/vLLM/Ollama/LiteLLM). Gemini stays
      the zero-config default. See `backend/llm/` + `test_llm_{service,factory,providers}.py`.
   ```
3. Conventions bullet, replace:
   ```
   - The LLM is Gemini via a hand-rolled `requests` call in `llm/gemini.py` (not the google SDK).
     Agents import `generate_sql_or_response_with_gemini` / `format_answer` directly — there is no
     provider seam yet.
   ```
   with:
   ```
   - LLM access goes through `llm/service.py` (`generate_sql_or_response` / `format_answer`) —
     never call a provider directly. New providers implement `llm/base.py:LLMProvider` and get
     wired in `llm/factory.py`. Config: `LLM_PROVIDER`/`LLM_MODEL`/`LLM_API_KEY`/`LLM_BASE_URL`.
   ```

- [ ] **Step 3: Update `docs/CODEBASE_AUDIT.md`** — find the EC-01 finding (search "EC-01") and mark it fixed in the same style the Phase-1 fixes use there (status ✅ + one line: "Fixed on branch phase2-pluggable-llm: provider protocol + gemini/openai_compat adapters + env-driven factory; llm/gemini.py deleted."). Update the Phase-1/Phase-2 status banner if it lists EC-01 as next up.

- [ ] **Step 4: Commit**

```bash
git add backend/.env.example CLAUDE.md docs/CODEBASE_AUDIT.md
git commit -m "Document the pluggable LLM provider config (EC-01)

.env.example: add LLM_* block, drop four env vars nothing reads.
CLAUDE.md + audit: EC-01 marked fixed, provider-seam conventions added.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Live end-to-end verification (real key, local only)

**Files:** none (verification only). Requires `backend/.env` with real `GEMINI_API_KEY` + `DATATALKER_API_KEY` (already present on this machine).

- [ ] **Step 1: Boot the live app**

```bash
cd backend && uv run uvicorn main:fastapi_app --port 8000
```
(Run in background; wait for `Application startup complete`.)

- [ ] **Step 2: Smoke the default (Gemini) path — success criterion 2**

```bash
curl -s -X POST http://127.0.0.1:8000/chat/ \
  -H "Authorization: Bearer <DATATALKER_API_KEY from backend/.env>" \
  -F "question=How many patients are there?" \
  -F "db_path=E:/GENAI-PROJECTS/DataTalker/backend/hospital.db"
```
Expected: HTTP 200, JSON containing a non-empty `answer`, a `sql` field with a single SELECT, and `results`.

- [ ] **Step 3: Misconfig gives a clear, generic failure — not a crash**

Stop the server. Restart with the provider forced to openai but unconfigured:
`LLM_PROVIDER=openai` (set env var for the process), same uvicorn command.
Repeat the curl. Expected: the app STARTS fine (config error surfaces at first use, not import); the response is a controlled answer whose text names `LLM_API_KEY` (the service's `RuntimeError` guard from Task 4 turns factory misconfig into a non-retryable error dict, which flows through the graph as a normal error answer). **No traceback in the HTTP body.**

- [ ] **Step 4: Stop the server, run the full suite one last time**

All 9 test files (list in Task 5 Step 5). Expected: all green. Nothing to commit — this task is verification only.

---

## Success criteria (from the spec)

1. `LLM_PROVIDER=openai` + `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL` runs `/chat/` against an OpenAI-compatible endpoint with no code change. *(Adapter verified by stubbed tests; a live openai-endpoint smoke is optional/manual — noted in the spec.)*
2. Default config (Gemini) behaves exactly as before; existing tests + live `/chat/` smoke green (Task 7).
3. `llm/gemini.py` is gone; no agent imports a concrete provider; new unit tests pass (Tasks 2–5).
