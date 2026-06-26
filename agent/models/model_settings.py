from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import ollama
except ModuleNotFoundError:  # pragma: no cover
    ollama = None


MODELS_CONFIG_PATH = Path("agent/config/models.yaml")
RUNTIME_MODEL_SETTINGS_PATH = Path("agent/runtime/model_settings.json")
FALLBACK_MAIN_MODEL = "qwen3:4b"


def get_default_main_model() -> str:
    if not MODELS_CONFIG_PATH.exists():
        return FALLBACK_MAIN_MODEL
    try:
        import yaml
    except ModuleNotFoundError:
        return FALLBACK_MAIN_MODEL
    raw = yaml.safe_load(MODELS_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    configured = (raw.get("main_model") or {}).get("model")
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    chat_model = raw.get("chat_model")
    if isinstance(chat_model, str) and chat_model.strip():
        return chat_model.strip()
    return FALLBACK_MAIN_MODEL


def get_main_model() -> str:
    if not RUNTIME_MODEL_SETTINGS_PATH.exists():
        return get_default_main_model()
    try:
        payload = json.loads(RUNTIME_MODEL_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return get_default_main_model()
    configured = payload.get("main_model")
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    return get_default_main_model()


def _extract_model_name(item: Any) -> str | None:
    if isinstance(item, dict):
        for key in ("model", "name"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
    for attr in ("model", "name"):
        value = getattr(item, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def list_ollama_models() -> list[str]:
    if ollama is None:
        raise ModuleNotFoundError("ollama is required")
    response = ollama.list()
    if isinstance(response, dict):
        models = response.get("models", response)
    else:
        models = getattr(response, "models", response)

    if isinstance(models, dict):
        models = models.get("models", [])
    if models is None:
        models = []
    if not isinstance(models, list):
        models = list(models)

    names: list[str] = []
    seen: set[str] = set()
    for item in models:
        name = _extract_model_name(item)
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def set_main_model(model_name: str) -> str:
    cleaned = (model_name or "").strip()
    if not cleaned:
        raise ValueError("Debes indicar un modelo válido.")
    available = list_ollama_models()
    if cleaned not in available:
        raise ValueError(f"El modelo no está instalado en Ollama: {cleaned}")
    RUNTIME_MODEL_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_MODEL_SETTINGS_PATH.write_text(
        json.dumps({"main_model": cleaned}, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return cleaned
