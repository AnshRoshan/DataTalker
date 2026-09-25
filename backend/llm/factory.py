# llm/factory.py
"""Env-driven provider selection. Read once, cached; misconfig raises a clear
error at FIRST USE (not import), naming the exact missing variable."""
import os
from functools import lru_cache

from dotenv import load_dotenv

from llm.base import LLMProvider
from llm.providers.gemini import GeminiProvider
from llm.providers.openai_compat import OpenAICompatProvider

load_dotenv()  # same pattern as old llm/gemini.py: honor backend/.env

_DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"
_DEFAULT_OPENROUTER_MODEL = "openai/gpt-4o-mini"


def _require(var: str, provider: str) -> str:
    value = os.getenv(var)
    if not value:
        raise RuntimeError(f"{var} is required for the '{provider}' LLM provider.")
    return value


def _model(provider: str, default: str) -> str:
    """Runtime selection (Settings -> model picker) wins over the env default."""
    from llm.selection import get_selected_model

    return get_selected_model() or default


@lru_cache(maxsize=1)
def get_provider() -> LLMProvider:
    name = (os.getenv("LLM_PROVIDER") or "gemini").strip().lower()
    raw_temp = os.getenv("LLM_TEMPERATURE")
    temperature = float(raw_temp) if raw_temp else None  # unset -> provider default

    if name == "gemini":
        return GeminiProvider(
            api_key=_require("GEMINI_API_KEY", name),
            model=_model(name, os.getenv("LLM_MODEL") or _DEFAULT_GEMINI_MODEL),
            temperature=temperature,
        )
    if name == "openai":
        # BYO endpoint: no sane default model, but a Settings pick counts as one.
        model = _model(name, os.getenv("LLM_MODEL") or "")
        if not model:
            raise RuntimeError(
                "LLM_MODEL is required for the 'openai' LLM provider (or choose one in Settings)."
            )
        return OpenAICompatProvider(
            api_key=_require("LLM_API_KEY", name),
            base_url=_require("LLM_BASE_URL", name),
            model=model,
            temperature=temperature,
        )
    if name == "openrouter":
        # OpenRouter preset: OpenAI wire format, one key in front of its whole catalog.
        # The base URL is fixed here on purpose — it is operator config, never request input.
        from llm.selection import OPENROUTER_BASE_URL

        return OpenAICompatProvider(
            api_key=_require("LLM_API_KEY", name),
            base_url=OPENROUTER_BASE_URL,
            model=_model(name, os.getenv("LLM_MODEL") or _DEFAULT_OPENROUTER_MODEL),
            temperature=temperature,
        )
    raise RuntimeError(
        f"Unknown LLM_PROVIDER '{name}' (expected 'gemini', 'openai', or 'openrouter')."
    )
