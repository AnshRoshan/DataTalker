# Design — Pluggable LLM Provider (EC-01)

**Date:** 2026-07-06 · **Status:** approved · **Phase:** 2 (sub-project A) · **Branch:** `phase2-pluggable-llm`

## Goal

Remove DataTalker's hardwiring to Google Gemini so a deployment can run on **any** model
(Gemini, OpenAI, Azure OpenAI, local vLLM/Ollama, LiteLLM-proxy, Bedrock-via-gateway) by
configuration alone. This is EC-01 from the audit and the core of the product's "BYO-LLM"
wedge. Scope is v1: **Gemini + an OpenAI-compatible adapter, no new dependencies.**

## Current state

All LLM access lives in `backend/llm/gemini.py`, which exposes two public functions the
agents import directly:

| Function | Called by | Returns |
|---|---|---|
| `generate_sql_or_response_with_gemini(schema, question, db_dialect)` | `agents/sql_writer.py`, `agents/sql_retry.py` | `{"sql": str}` \| `{"response": str}` \| `{"error": str, "retryable": bool}` |
| `format_answer(question, result)` | `agents/answer.py` | `{"answer": str, "follow_up_questions": list[str]}` (or `{"error": …}`) |

Internally the file already separates concerns that are **provider-agnostic** from the one
part that is Gemini-specific:
- `_get_system_instruction_for_sql(...)` — builds the SQL prompt (agnostic)
- `_parse_and_validate_gemini_response(text)` — parses model text → the result dict (agnostic)
- the `requests.post(...)` to `generativelanguage.googleapis.com/...:generateContent` — **Gemini-specific**

Only the HTTP call needs to vary per provider. That makes this a clean extraction, not a rewrite.

## Design

### Module layout

```
backend/llm/
  base.py              LLMProvider protocol
  providers/
    __init__.py
    gemini.py          GeminiProvider
    openai_compat.py   OpenAICompatProvider
  factory.py           get_provider()  (config-driven, cached)
  prompts.py           SQL + answer system-instruction builders (moved out of gemini.py).
                       While moving: fix the SQL prompt line "Multiple statements can be
                       separated by semicolons" → instruct ONE read-only SELECT/WITH only
                       (it contradicts the SEC-01 validator and wastes retries).
  service.py           generate_sql_or_response(...) + format_answer(...)  (same contracts)
```
`backend/llm/gemini.py` is **deleted**. The three agent imports switch to `llm.service`.

### LLMProvider protocol (`base.py`)

```python
class LLMProvider(Protocol):
    def complete(self, system: str, user: str) -> str:
        """Send one system+user turn and return the model's raw text. Raises LLMError
        (with a .retryable flag) on transport failure; the service layer maps that to
        a retryable error dict."""
```

Model and temperature are **constructor config** on each provider, not per-call kwargs — no
call site varies them per call (YAGNI; `max_tokens` dropped for the same reason).

Providers return **raw text**; all prompt-building and JSON parsing stays in the service
layer, so adapters are tiny and share zero logic.

### Providers

- **`GeminiProvider`** — moves the existing `requests.post` to
  `.../models/{model}:generateContent` with the `x-goog-api-key` header (already the case
  after PR-05), extracts `candidates[0].content.parts[0].text`. Config: `api_key` (from
  `GEMINI_API_KEY`), `model`, `temperature`, timeout/retries reuse the current constants.
- **`OpenAICompatProvider`** — `POST {base_url}/chat/completions` with
  `Authorization: Bearer {api_key}`, body `{model, messages:[{role:system},{role:user}], temperature}`,
  extracts `choices[0].message.content`. `base_url` covers OpenAI (`https://api.openai.com/v1`),
  Azure OpenAI, local vLLM/Ollama, a LiteLLM proxy, or a Bedrock gateway.

**The retry loop lives ONCE in the service layer, wrapped around `complete()` + parse** (reusing
the current constants: `MAX_RETRIES=3`, `RETRY_DELAY_SECONDS` backoff). Rationale: the current
Gemini loop retries **parse failures too** (model returned bad JSON / missing keys —
`gemini.py:219`), not just transport errors, and parsing happens above the provider. Putting
retry in each provider would silently lose bad-JSON retry (`SQLRetryAgent` only covers
empty-results-after-execution, not malformed model output). With the loop in the service,
providers stay trivial — one POST with a timeout, raise on failure — and both providers get an
identical retry policy for free. Side effect (benign, deliberate): `format_answer` gains the
same retry loop (today it has none). On final failure the service returns a generic error dict
(no raw upstream body to the client — consistent with PR-05).

### Factory (`factory.py`)

`get_provider()` reads config once and returns a cached singleton (module-level
`functools.lru_cache` or a guarded global). Selection:

| `LLM_PROVIDER` | Provider | Required config |
|---|---|---|
| unset or `gemini` | `GeminiProvider` | `GEMINI_API_KEY` |
| `openai` | `OpenAICompatProvider` | `LLM_API_KEY`, `LLM_BASE_URL` |

Missing required config raises a clear error at first use (`"LLM_BASE_URL is required for
the 'openai' provider"`), not a vague 500.

### Service (`service.py`)

Holds the two public functions with **unchanged signatures and return dicts**:
- `generate_sql_or_response(schema, question, db_dialect)` — build the SQL system prompt
  (`prompts.build_sql_instruction`), call `get_provider().complete(system, user)`, parse via
  the moved `_parse_and_validate_response`, return `{"sql"|"response"|"error", ...}`.
- `format_answer(question, result)` — build the answer prompt, call the provider, parse to
  `{"answer", "follow_up_questions"}`.

A transport exception from the provider becomes `{"error": "The language model is
unavailable.", "retryable": True}` (generic message; detail logged server-side).

### Agent changes (the only touch outside `llm/`)

- `agents/sql_writer.py`: `from llm.gemini import generate_sql_or_response_with_gemini`
  → `from llm.service import generate_sql_or_response`; update the one call.
- `agents/sql_retry.py`: same.
- `agents/answer.py`: `from llm.gemini import format_answer` → `from llm.service import format_answer`.
- `agents/sql_retry.py` (drive-by, 3-line deletion): `_analyze_failure` currently suggests
  multi-statement SQL ("Or combine: SELECT …; SELECT …", "Generate multiple queries") — the
  SEC-01 validator rejects those unconditionally, so every such retry is a guaranteed failure.
  Remove the multi-query suggestions.

The LangGraph wiring and every state key are untouched — the return contracts are identical.

## Config (env, backward-compatible)

| Var | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `gemini` | `gemini` \| `openai` |
| `LLM_MODEL` | `gemini-1.5-flash` (gemini) | **required** for `openai` — a BYO endpoint has no sane universal default |
| `LLM_TEMPERATURE` | unset | unset → provider default (matches pre-refactor behavior: no temperature sent) |
| `GEMINI_API_KEY` | — | required for gemini (unchanged) |
| `LLM_API_KEY` | — | required for openai |
| `LLM_BASE_URL` | — | required for openai (e.g. `https://api.openai.com/v1`) |

**Backward compatibility:** with `LLM_PROVIDER` unset and `GEMINI_API_KEY` present, the app
behaves exactly as before. Documented in `.env.example`.

**Deliberate behavior change:** SQL generation and answer formatting now share one model
(`LLM_MODEL`) instead of two hardcoded Gemini models (`gemini-1.5-flash` +
`gemini-2.0-flash-lite`). Negligible quality impact; simpler and provider-portable.

## Error handling

- Transport/timeout/HTTP-error from a provider → service returns `{"error": <generic>,
  "retryable": True}`; full detail (status, body) logged at `warning`, never returned to the client.
- Empty / unparseable model output → existing parse path returns `{"error": …, "retryable": True}`.
- Missing/invalid provider config → clear error naming the missing var.

## Testing

A `FakeProvider` (returns canned strings, no network) makes the seam unit-testable:

- `test_llm_service.py` — with a `FakeProvider`: `generate_sql_or_response` parses
  `{"sql":…}`, `{"response":…}`, and malformed → `{"error":…}`; `format_answer` parses
  answer + follow-ups; a provider that raises → `{"error", "retryable": True}`; **retry
  behavior**: a FakeProvider returning bad JSON then good JSON succeeds on the second
  attempt (proves the parse-retry loop survived the refactor).
- `test_llm_factory.py` — `LLM_PROVIDER=openai` → `OpenAICompatProvider`; unset/`gemini` →
  `GeminiProvider`; missing `LLM_BASE_URL` for openai → clear error.

Assert-based, run with plain `python` (matches the existing `backend/test_*.py` suite). No
provider network calls in tests. Existing `/schema/` e2e stays green; a live `/chat/` smoke
test (Gemini or an OpenAI-compatible endpoint) is a manual step.

## Out of scope (later phases)

- LiteLLM / native OpenAI/Anthropic SDKs (v1 is two hand-rolled adapters).
- Per-tenant / per-request model selection (belongs to multi-tenancy, EC-04).
- Streaming responses (Phase 3 output work).
- Separate models for SQL vs answer (single `LLM_MODEL` in v1).
- Retry/cost/rate-limit policy beyond the existing constants.

## Success criteria

1. `LLM_PROVIDER=openai` + `LLM_BASE_URL`/`LLM_API_KEY` runs `/chat/` against an
   OpenAI-compatible endpoint with no code change.
2. Default config (Gemini) behaves exactly as before; existing tests + `/schema/` e2e green.
3. `llm/gemini.py` is gone; no agent imports a concrete provider; new unit tests pass.
