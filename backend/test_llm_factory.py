# backend/test_llm_factory.py
# Assert-based self-check for env-driven provider selection (EC-01).
#   uv run --directory backend python test_llm_factory.py
import os

from llm.factory import get_provider, reset_provider_cache
from llm.providers.gemini import GeminiProvider
from llm.providers.openai_compat import OpenAICompatProvider


def reset(**env):
    """Set exactly the LLM env we want, clear the factory cache."""
    for var in ("LLM_PROVIDER", "LLM_MODEL", "LLM_TEMPERATURE", "GEMINI_API_KEY", "LLM_API_KEY", "LLM_BASE_URL"):
        os.environ.pop(var, None)
    os.environ.update(env)
    reset_provider_cache()


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
