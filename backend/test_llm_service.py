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

# JSON embedded in prose -> the regex fallback extracts it (pre-refactor behavior)
with_fake('Sure, here is the SQL: {"sql": "SELECT 5"} hope that helps!')
assert svc.generate_sql_or_response("s", "q")["sql"] == "SELECT 5"

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

# a provider hint (rejected credentials) replaces the generic message — actionable,
# secret-free, and tried once.
fake = with_fake(LLMError("Gemini API error 400: API key not valid", retryable=False, hint="Set a valid GEMINI_API_KEY."))
r = svc.generate_sql_or_response("s", "q")
assert r["error"] == "Set a valid GEMINI_API_KEY." and r["retryable"] is False and fake.calls == 1

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
