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


def expect_llm_error(fn, retryable, hint=None):
    try:
        fn()
    except LLMError as e:
        assert e.retryable is retryable, f"retryable={e.retryable}, want {retryable}"
        if hint is not None:
            assert hint in e.hint, f"hint {e.hint!r} should name {hint!r}"
        else:
            assert e.hint == "", f"unexpected hint {e.hint!r}"
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

# rejected key (Gemini answers this with 400 + "API key not valid") -> NON-retryable + hint
gemini_mod.requests = _FakeRequests(_Resp(400, {"error": {"message": "API key not valid."}}))
expect_llm_error(lambda: p.complete("s", "u"), retryable=False, hint="GEMINI_API_KEY")

# 403 is auth too, even when the body says nothing about keys
gemini_mod.requests = _FakeRequests(_Resp(403, {"error": {"status": "PERMISSION_DENIED"}}))
expect_llm_error(lambda: p.complete("s", "u"), retryable=False, hint="GEMINI_API_KEY")

# a 400 about the REQUEST (not the key) stays retryable and hintless
gemini_mod.requests = _FakeRequests(_Resp(400, {"error": {"message": "Cannot extract a valid JSON"}}))
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

# rejected key on an OpenAI-compatible gateway (401) -> NON-retryable + hint naming the vars
openai_mod.requests = _FakeRequests(_Resp(401, {"error": {"message": "Incorrect API key provided"}}))
expect_llm_error(lambda: q.complete("s", "u"), retryable=False, hint="LLM_API_KEY")

print("llm_providers: all assertions passed")
