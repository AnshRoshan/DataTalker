# llm/selection.py
"""Runtime model selection + the provider's model catalog.

The LLM *provider* stays an env/deploy decision (its base URL and key come from
the operator's environment, never from a request); what a deployment may change
at runtime is WHICH model that provider talks to — useful for OpenRouter and
any OpenAI-compatible gateway, where one key fronts hundreds of models.

Selection is persisted to <data_dir>/model_selection.json (same pattern as the
connections registry) and applied by llm/factory.get_provider(), whose cache is
cleared on every write. Model ids are validated against a conservative charset
so nothing user-shaped reaches the catalog URL.
"""
import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_SELECTION_FILENAME = "model_selection.json"
_TIMEOUT_SECONDS = 20

# OpenRouter speaks the OpenAI wire format; the preset saves operators from
# typing the base URL (and keeps it fixed server-side rather than request-supplied).
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:-]{0,119}$")


class SelectionError(ValueError):
    """Raised for an unusable model id (surfaced to the client as a 400)."""


def _selection_path() -> Path:
    from core.settings import get_settings

    return Path(get_settings().data_dir) / _SELECTION_FILENAME


def provider_name() -> str:
    """Which provider is answering: the caller's bring-your-own pick, else env."""
    from llm.request_provider import current_credentials

    creds = current_credentials()
    if creds is not None:
        return creds.provider
    return (os.getenv("LLM_PROVIDER") or "gemini").strip().lower()


def get_selected_model() -> Optional[str]:
    """The runtime-selected model, or None when the env/default applies."""
    path = _selection_path()
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("model selection %s unreadable (%s); ignoring", path, e)
        return None
    model = raw.get("model") if isinstance(raw, dict) else None
    if isinstance(model, str) and _MODEL_ID_RE.match(model):
        return model
    return None


def set_selected_model(model: str) -> str:
    """Persist the selection and rebuild the provider. Raises SelectionError on junk input."""
    model = (model or "").strip()
    if not _MODEL_ID_RE.match(model):
        raise SelectionError(
            "Model id must be 1-120 characters of letters, digits, and . _ / : -"
        )
    path = _selection_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"model": model}, f, indent=2)
        os.replace(tmp, path)

    from llm.factory import reset_provider_cache

    reset_provider_cache()
    logger.info("LLM model selected: %s (provider: %s)", model, provider_name())
    return model


def clear_selected_model() -> None:
    path = _selection_path()
    with _lock:
        if path.is_file():
            path.unlink()

    from llm.factory import reset_provider_cache

    reset_provider_cache()


def _get(url: str, headers: Dict[str, str]) -> Any:
    response = requests.get(url, headers=headers, timeout=_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def _ids_from(payload: Any, key: str, prefix_strip: str = "") -> List[Dict[str, str]]:
    """Normalize the two catalog shapes (OpenAI {data:[{id,name}]}, Gemini {models:[{name}]})
    into [{id, label}], dropping entries without an id."""
    items = payload.get(key) if isinstance(payload, dict) else None
    out: List[Dict[str, str]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or item.get("name") or "").strip()
        if not model_id:
            continue
        bare = model_id.removeprefix(prefix_strip) if prefix_strip else model_id
        label = str(item.get("name") or bare).strip()
        out.append({"id": bare, "label": label})
    return out


def list_models() -> Dict[str, Any]:
    """Ask the configured provider which models it serves.

    Never raises: a listing failure returns the configured model plus an `error`
    string, so the Settings UI can still show what is in use.
    """
    from llm.factory import get_provider

    name = provider_name()
    try:
        provider = get_provider()
    except Exception as e:
        # Misconfigured provider: the UI shows the factory's message verbatim
        # (it names env vars and never their values).
        return {"provider": name, "model": None, "models": [], "error": str(e)}

    current = getattr(provider, "model", None)
    api_key = getattr(provider, "api_key", "")
    try:
        if name == "gemini":
            payload = _get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                {"x-goog-api-key": api_key},
            )
            models = [m for m in _ids_from(payload, "models", prefix_strip="models/") if "gemini" in m["id"]]
        else:
            base_url = getattr(provider, "base_url", OPENROUTER_BASE_URL).rstrip("/")
            payload = _get(f"{base_url}/models", {"Authorization": f"Bearer {api_key}"})
            models = _ids_from(payload, "data")
    except (requests.RequestException, ValueError) as e:
        logger.warning("model catalog for %s unavailable: %s", name, e)
        return {"provider": name, "model": current, "models": [], "error": None}

    return {"provider": name, "model": current, "models": models[:200], "error": None}
