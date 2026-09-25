# backend/test_llm_selection.py
# Assert-based self-check for the OpenRouter preset + runtime model selection.
# No network: the catalog fetch is stubbed.
#   uv run --directory backend python test_llm_selection.py
import os
import tempfile

from llm.factory import get_provider
from llm.providers.openai_compat import OpenAICompatProvider
from llm.selection import (
    OPENROUTER_BASE_URL,
    SelectionError,
    clear_selected_model,
    get_selected_model,
    list_models,
    set_selected_model,
)
from llm.service import generate_sql_or_response

os.environ["DATATALKER_DATA_DIR"] = tempfile.mkdtemp(prefix="dt-sel-test-")
from core.settings import get_settings  # noqa: E402

get_settings.cache_clear()


def reset(**env):
    for var in ("LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY", "LLM_BASE_URL", "GEMINI_API_KEY"):
        os.environ.pop(var, None)
    os.environ.update(env)
    clear_selected_model()
    get_provider.cache_clear()


# --- the OpenRouter preset: OpenAI wire format, base URL fixed server-side ---
reset(LLM_PROVIDER="openrouter", LLM_API_KEY="or-key")
p = get_provider()
assert isinstance(p, OpenAICompatProvider)
assert p.base_url == OPENROUTER_BASE_URL == "https://openrouter.ai/api/v1"
assert p.model == "openai/gpt-4o-mini"

reset(LLM_PROVIDER="openrouter", LLM_API_KEY="or-key", LLM_MODEL="anthropic/claude-sonnet-4.5")
assert get_provider().model == "anthropic/claude-sonnet-4.5"

reset(LLM_PROVIDER="openrouter")


def expect_error(naming):
    try:
        get_provider()
    except RuntimeError as e:
        assert naming in str(e), f"expected {naming!r} in {e}"
        return
    raise AssertionError(f"expected RuntimeError naming {naming!r}")


expect_error("LLM_API_KEY")

# unknown provider names the accepted set (openrouter included)
reset(LLM_PROVIDER="banana", GEMINI_API_KEY="g")
expect_error("openrouter")

# --- runtime selection overrides the env default, for any provider ---
reset(LLM_PROVIDER="openrouter", LLM_API_KEY="or-key", LLM_MODEL="openai/gpt-4o-mini")
assert get_selected_model() is None
assert get_provider().model == "openai/gpt-4o-mini"
assert set_selected_model("meta-llama/llama-3.3-70b-instruct") == "meta-llama/llama-3.3-70b-instruct"
assert get_selected_model() == "meta-llama/llama-3.3-70b-instruct"
assert get_provider().model == "meta-llama/llama-3.3-70b-instruct", "selection must reach the provider"
clear_selected_model()
assert get_selected_model() is None and get_provider().model == "openai/gpt-4o-mini"

# junk model ids are rejected before they ever hit a file or a URL
for bad in ("", "  ", "has space", "../etc/passwd", "a" * 200, "drop'); --"):
    try:
        set_selected_model(bad)
    except SelectionError:
        continue
    raise AssertionError(f"{bad!r} should have been rejected")

# --- catalog listing normalizes both shapes (provider requests are stubbed) ---
import llm.selection as sel  # noqa: E402

reset(LLM_PROVIDER="openrouter", LLM_API_KEY="or-key", LLM_MODEL="openai/gpt-4o-mini")
captured = {}


def fake_get(url, headers):
    captured["url"] = url
    captured["headers"] = headers
    return {"data": [{"id": "openai/gpt-4o-mini", "name": "GPT-4o mini"}, {"id": "no-name"}]}


sel._get = fake_get
out = list_models()
assert captured["url"] == "https://openrouter.ai/api/v1/models"
assert captured["headers"] == {"Authorization": "Bearer or-key"}
assert out["provider"] == "openrouter" and out["model"] == "openai/gpt-4o-mini"
assert out["models"] == [
    {"id": "openai/gpt-4o-mini", "label": "GPT-4o mini"},
    {"id": "no-name", "label": "no-name"},
]
assert out["error"] is None

# listing failure -> never raises, the UI just gets no list
def boom(url, headers):
    raise sel.requests.RequestException("offline")


sel._get = boom
out = list_models()
assert out["models"] == [] and out["error"] is None and out["model"] == "openai/gpt-4o-mini"

# misconfigured provider -> the factory's own clear message, no crash
reset(LLM_PROVIDER="openrouter")
sel._get = fake_get
out = list_models()
assert "LLM_API_KEY" in out["error"] and out["models"] == []

# --- a rejected key surfaces the provider hint through the service, once ---
reset(LLM_PROVIDER="openrouter", LLM_API_KEY="or-key", LLM_MODEL="m")
import llm.service as svc  # noqa: E402
from llm.base import LLMError  # noqa: E402

svc.RETRY_DELAY_SECONDS = 0
calls = {"n": 0}


class OneShot:
    def complete(self, system, user):
        calls["n"] += 1
        raise LLMError("HTTP 401", retryable=False, hint="The endpoint rejected the key — check LLM_API_KEY.")


_fake = OneShot()
svc.get_provider = lambda: _fake
r = generate_sql_or_response("s", "q")
assert "LLM_API_KEY" in r["error"] and r["retryable"] is False and calls["n"] == 1

reset()
print("llm_selection: all assertions passed")
