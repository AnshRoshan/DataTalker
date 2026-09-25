# backend/test_llm_byok.py
# Assert-based self-check for bring-your-own-key LLM credentials (per-request, in-memory).
#   uv run --directory backend python test_llm_byok.py
import json
import logging
import os

from llm import request_provider as rp
from llm.factory import get_provider
from llm.providers.gemini import GeminiProvider
from llm.providers.openai_compat import OpenAICompatProvider
from llm.selection import provider_name

# ---------- header parsing ----------
assert rp.parse_headers(None, None, None) is None
assert rp.parse_headers("", "", "") is None

try:
    rp.parse_headers("banana", "k", None)
    raise AssertionError("unknown provider must raise")
except ValueError as e:
    assert "banana" in str(e) and "openrouter" in str(e), e

try:
    rp.parse_headers("openrouter", "   ", None)
    raise AssertionError("blank key must raise")
except ValueError as e:
    assert "X-LLM-Key" in str(e), e

creds = rp.parse_headers("OpenRouter", "  sk-or-abc  ", " anthropic/claude-sonnet-4.5 ")
assert creds.provider == "openrouter" and creds.api_key == "sk-or-abc"
assert creds.model == "anthropic/claude-sonnet-4.5"

# ---------- provider resolution ----------
for var in ("LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY", "LLM_BASE_URL", "GEMINI_API_KEY"):
    os.environ.pop(var, None)
os.environ["LLM_PROVIDER"] = "gemini"
os.environ["GEMINI_API_KEY"] = "operator-gemini-key"

# operator path still works
p = get_provider()
assert isinstance(p, GeminiProvider) and p.api_key == "operator-gemini-key"

# a caller's key wins for their request only, and picks a FIXED base URL
tok = rp.set_credentials(rp.parse_headers("openai", "sk-user", "gpt-4o"))
q = get_provider()
assert isinstance(q, OpenAICompatProvider) and q.api_key == "sk-user" and q.model == "gpt-4o"
assert q.base_url == "https://api.openai.com/v1", "callers must not steer the base URL"
assert provider_name() == "openai", "selection/catalog must follow the caller's provider"
rp.reset_credentials(tok)

# ...and does not leak into the next request (no cache poisoning, no context carry-over)
p2 = get_provider()
assert isinstance(p2, GeminiProvider) and p2.api_key == "operator-gemini-key"
assert provider_name() == "gemini"

# an unknown provider can never be built even by direct construction
tok = rp.set_credentials(rp.RequestLLMCredentials("ollama", "k", "m"))
try:
    get_provider()
    raise AssertionError("unpreset provider must not resolve")
except (KeyError, RuntimeError):
    pass
finally:
    rp.reset_credentials(tok)

# ---------- the key must never be logged or returned ----------
import llm.providers.openai_compat as oc  # noqa: E402


class _Resp:
    status_code = 401
    text = json.dumps({"error": {"message": "Incorrect API key provided"}})

    def json(self):
        return json.loads(self.text)


class _FakeRequests:
    exceptions = __import__("requests").exceptions

    def post(self, url, **kw):
        return _Resp()


oc.requests = _FakeRequests()
records = []


class _Capture(logging.Handler):
    def emit(self, record):
        records.append(self.format(record))


import llm.service as svc  # noqa: E402

svc.RETRY_DELAY_SECONDS = 0
provider = OpenAICompatProvider("sk-supers3cret", "https://api.openai.com/v1", "gpt-4o")
svc.get_provider = lambda: provider
handler = _Capture()
handler.setFormatter(logging.Formatter("%(name)s %(levelname)s %(message)s"))
logging.getLogger().addHandler(handler)


def ask():
    return svc.generate_sql_or_response("schema", "question")


# operator-key rejection -> the hint points at the server config
result = ask()
assert "LLM_API_KEY" in result["error"], result

# same rejection while the caller brought their own key -> they get told to fix THEIRS,
# because a visitor of a deployed instance has no backend/.env to edit.
tok = rp.set_credentials(rp.parse_headers("openai", "sk-supers3cret", "gpt-4o"))
byok = ask()
rp.reset_credentials(tok)
assert "Settings" in byok["error"] and ".env" not in byok["error"], byok

logging.getLogger().removeHandler(handler)

assert "error" in result, result
blob = json.dumps(result) + json.dumps(byok) + "".join(records)
assert "sk-supers3cret" not in blob, "the caller's key must not appear in responses or logs"

print("llm_byok: all assertions passed")
