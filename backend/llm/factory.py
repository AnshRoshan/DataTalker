# llm/factory.py
"""Provider resolution. Two sources, in order:

1. Bring-your-own-key — the caller sent X-LLM-Provider / X-LLM-Key on this request
   (see llm/request_provider.py). Built fresh, never cached, lives for the request.
2. The operator's environment — read once and cached; misconfig raises a clear error
   at FIRST USE (not import), naming the exact missing variable.
"""
import os
from functools import lru_cache

from dotenv import load_dotenv

from llm.base import LLMProvider
from llm.providers.gemini import GeminiProvider
from llm.providers.openai_compat import OpenAICompatProvider
from llm.request_provider import DEFAULT_MODELS, PRESET_BASE_URLS, current_credentials

load_dotenv()  # same pattern as old llm/gemini.py: honor backend/.env

_DEFAULT_GEMINI_MODEL = DEFAULT_MODELS["gemini"]
_DEFAULT_OPENROUTER_MODEL = DEFAULT_MODELS["openrouter"]


def _build(name: str, api_key: str, model: str, base_url: str | None, temperature: float | None) -> LLMProvider:
    if name == "gemini":
        return GeminiProvider(api_key=api_key, model=model, temperature=temperature)
    return OpenAICompatProvider(
        api_key=api_key, base_url=base_url, model=model, temperature=temperature
    )


def get_provider() -> LLMProvider:
    creds = current_credentials()
    if creds is not None:
        return _build(
            name=creds.provider,
            api_key=creds.api_key,
            model=creds.model or DEFAULT_MODELS[creds.provider],
            base_url=PRESET_BASE_URLS[creds.provider],
            temperature=_env_temperature(),
        )
    return _env_provider()


def reset_provider_cache() -> None:
    """Drop the cached operator provider — after a Settings model change, or in tests."""
    _env_provider.cache_clear()


def _env_temperature() -> float | None:
    raw_temp = os.getenv("LLM_TEMPERATURE")
    return float(raw_temp) if raw_temp else None  # unset -> provider default


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
def _env_provider() -> LLMProvider:
    name = (os.getenv("LLM_PROVIDER") or "gemini").strip().lower()
    temperature = _env_temperature()

    if name == "gemini":
        return _build(
            name=name,
            api_key=_require("GEMINI_API_KEY", name),
            model=_model(name, os.getenv("LLM_MODEL") or _DEFAULT_GEMINI_MODEL),
            base_url=None,
            temperature=temperature,
        )
    if name == "openai":
        # BYO endpoint: the operator may point at any OpenAI-compatible server, so the
        # base URL is required here (and only ever comes from the environment).
        model = _model(name, os.getenv("LLM_MODEL") or "")
        if not model:
            raise RuntimeError(
                "LLM_MODEL is required for the 'openai' LLM provider (or choose one in Settings)."
            )
        return _build(
            name=name,
            api_key=_require("LLM_API_KEY", name),
            model=model,
            base_url=_require("LLM_BASE_URL", name),
            temperature=temperature,
        )
    if name == "openrouter":
        from llm.selection import OPENROUTER_BASE_URL

        return _build(
            name=name,
            api_key=_require("LLM_API_KEY", name),
            model=_model(name, os.getenv("LLM_MODEL") or _DEFAULT_OPENROUTER_MODEL),
            base_url=OPENROUTER_BASE_URL,
            temperature=temperature,
        )
    raise RuntimeError(
        f"Unknown LLM_PROVIDER '{name}' (expected 'gemini', 'openrouter', or 'openai')."
    )
