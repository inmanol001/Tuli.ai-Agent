from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from agent.models.ollama_client import OllamaClient


DEFAULT_YOUTUBE_QUERY = "documental corto interesante"
DEFAULT_WEB_QUERY = "temas interesantes de tecnología y ciencia"


SENTINEL_VALUES = {
    "",
    "__open_ended__",
    "random",
    "random video",
    "video random",
    "video random entretenido",
    "cualquiera",
    "cualquier cosa",
    "algo interesante",
    "algo",
}


INTEREST_QUERY_MAP = [
    (
        ("agente", "agentes", "ia local", "ollama", "tool calling", "openclaw", "tuli", "lia"),
        {
            "youtube": "agentes de inteligencia artificial locales",
            "auto": "agentes de inteligencia artificial locales",
            "web": "agentes de inteligencia artificial locales",
        },
    ),
    (
        ("inteligencia artificial", "ia", "ai", "tecnologia", "tecnología", "tech"),
        {
            "youtube": "tecnología inteligencia artificial curiosidades",
            "auto": "noticias tecnología inteligencia artificial",
            "web": "noticias tecnología inteligencia artificial",
        },
    ),
    (
        ("programacion", "programación", "python", "codigo", "código", "desarrollo"),
        {
            "youtube": "programación python proyectos interesantes",
            "auto": "programación python proyectos interesantes",
            "web": "programación python proyectos interesantes",
        },
    ),
    (
        ("diseño", "diseno", "design", "branding", "canva", "photoshop", "illustrator"),
        {
            "youtube": "inspiración diseño gráfico branding",
            "auto": "inspiración diseño gráfico branding",
            "web": "inspiración diseño gráfico branding",
        },
    ),
    (
        ("misterio", "terror", "casos", "inexplicable", "inexplicables", "documental"),
        {
            "youtube": "documental misterio casos inexplicables",
            "auto": "historias de misterio casos inexplicables",
            "web": "historias de misterio casos inexplicables",
        },
    ),
]


def normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def is_sentinel_query(value: str) -> bool:
    return normalize_text(value) in SENTINEL_VALUES


def resolve_open_ended_search_query(
    *,
    target: str = "auto",
    query: str = "",
    topic_hint: str = "",
    user_context: str = "",
    fallback: str | None = None,
) -> str:
    """Resolve random/open-ended searches into safe useful queries.

    Priority:
    1. Main model through agent.models.ollama_client.OllamaClient.
    2. Heuristic interest map fallback.
    3. Safe default fallback.

    Never returns "__open_ended__".
    """

    clean_target = normalize_text(target) or "auto"
    clean_query = normalize_text(query)
    clean_topic = normalize_text(topic_hint)
    clean_context = normalize_text(user_context)

    meaningful_query = clean_query if clean_query and not is_sentinel_query(clean_query) else ""
    meaningful_topic = clean_topic if clean_topic and not is_sentinel_query(clean_topic) else ""

    main_model_query = _query_from_main_model(
        target=clean_target,
        query=meaningful_query,
        topic_hint=meaningful_topic,
        user_context=clean_context,
    )
    if main_model_query:
        return main_model_query

    if meaningful_topic:
        return _expand_topic(meaningful_topic, clean_target)

    if meaningful_query:
        return _expand_topic(meaningful_query, clean_target)

    context_query = _query_from_context(clean_context, clean_target)
    if context_query:
        return context_query

    if fallback:
        return fallback

    if clean_target == "youtube":
        return DEFAULT_YOUTUBE_QUERY

    return DEFAULT_WEB_QUERY


def _query_from_main_model(
    *,
    target: str,
    query: str,
    topic_hint: str,
    user_context: str,
) -> str:
    """Use Tuli's internal OllamaClient with the configured main model.

    This avoids creating a separate hidden model path. It uses the same internal
    client used by the rest of the app.
    """

    if os.getenv("TULI_SEARCH_RESOLVER_DISABLE_MAIN_MODEL", "").lower() in {"1", "true", "yes"}:
        return ""

    if not query and not topic_hint and not user_context:
        return ""

    model = _main_model_name()
    if not model:
        return ""

    messages = _build_query_messages(
        target=target,
        query=query,
        topic_hint=topic_hint,
        user_context=user_context,
    )

    try:
        raw = OllamaClient().chat(
            model,
            messages,
            think=False,
            options={
                "temperature": 0.25,
                "num_predict": 80,
            },
        )
    except Exception:
        return ""

    return _sanitize_model_query(raw)


# Backward-compatible alias for old tests/scripts that imported this name.
def _query_from_local_model(
    *,
    target: str,
    query: str,
    topic_hint: str,
    user_context: str,
) -> str:
    return _query_from_main_model(
        target=target,
        query=query,
        topic_hint=topic_hint,
        user_context=user_context,
    )


def _main_model_name() -> str:
    """Return the main local Ollama model used by Tuli.

    Important:
    - This uses local Ollama models only.
    - Env/config can override it.
    - Never return config keys like "provider:".
    """

    for key in (
        "TULI_MAIN_MODEL",
        "MAIN_MODEL",
        "TULI_MODEL",
        "OLLAMA_MODEL",
    ):
        value = os.getenv(key)
        if value and _looks_like_ollama_model_name(value.strip()):
            return value.strip()

    config_guess = _model_from_config_files()
    if config_guess and _looks_like_ollama_model_name(config_guess):
        return config_guess

    return "llama3.1:8b"



def _model_from_config_files() -> str:
    """Best-effort parse of likely config files.

    We avoid requiring yaml imports. This only extracts common text patterns.
    """

    candidates = [
        Path("agent/config/models.yaml"),
        Path("agent/config/model.yaml"),
        Path("agent/config/llm.yaml"),
        Path("agent/config/settings.yaml"),
        Path("agent/config/agent.yaml"),
        Path("agent/config/config.yaml"),
        Path(".env"),
        Path(".env.local"),
    ]

    text_parts: list[str] = []
    for path in candidates:
        if path.exists() and path.is_file():
            try:
                text_parts.append(path.read_text(errors="ignore"))
            except Exception:
                pass

    text = "\n".join(text_parts)
    if not text.strip():
        return ""

    patterns = [
        r"(?:main_model|MAIN_MODEL|tuli_model|TULI_MODEL|model)\s*[:=]\s*[\"']?([A-Za-z0-9_./:-]+)",
        r"(?:chat_model|CHAT_MODEL|default_model|DEFAULT_MODEL)\s*[:=]\s*[\"']?([A-Za-z0-9_./:-]+)",
    ]

    bad_values = {"true", "false", "null", "none", "ollama", "models", "model"}

    for pattern in patterns:
        for match in re.finditer(pattern, text):
            value = match.group(1).strip().strip("\"'")
            if value and value.lower() not in bad_values and ":" in value:
                return value

    return ""



def _looks_like_ollama_model_name(value: str) -> bool:
    value = (value or "").strip()

    if not value:
        return False

    bad_values = {
        "true",
        "false",
        "null",
        "none",
        "ollama",
        "models",
        "model",
        "provider",
        "provider:",
        "completion",
        "tools",
        "thinking",
    }

    if value.lower() in bad_values:
        return False

    if value.endswith(":") and value.count(":") == 1:
        return False

    if ":" in value:
        left, right = value.rsplit(":", 1)
        return bool(left.strip()) and bool(right.strip())

    known_prefixes = ("qwen", "llama", "mistral", "gemma", "phi", "deepseek", "allenporter/")
    return value.lower().startswith(known_prefixes)

def _build_query_messages(
    *,
    target: str,
    query: str,
    topic_hint: str,
    user_context: str,
) -> list[dict[str, str]]:
    platform = "YouTube" if target == "youtube" else "internet"

    system = (
        "Eres un resolvedor de búsquedas para Tuli. "
        "Tu única tarea es convertir una petición abierta/random en UNA búsqueda corta y útil. "
        "Responde solo con la búsqueda final. No expliques. No uses JSON. "
        "No uses comillas. No incluyas '__open_ended__'. Máximo 8 palabras."
    )

    user = f"""Plataforma: {platform}
Target interno: {target}
Query original: {query or "(vacía/open-ended)"}
Topic hint: {topic_hint or "(ninguno)"}

Contexto/memoria del usuario:
{user_context or "(sin contexto)"}

Reglas:
- Si hay Topic hint, respétalo por encima del contexto.
- Si no hay Topic hint, usa el contexto/memoria para escoger algo que probablemente le interese al usuario.
- Devuelve solo la búsqueda final.

Búsqueda final:"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _sanitize_model_query(raw: str) -> str:
    text = str(raw or "").strip()

    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I).strip()

    try:
        parsed: Any = json.loads(text)
        if isinstance(parsed, dict):
            for key in ("query", "search_query", "q", "busqueda", "búsqueda"):
                if key in parsed:
                    text = str(parsed[key])
                    break
    except Exception:
        pass

    text = text.strip()
    text = text.splitlines()[0] if text.splitlines() else ""
    text = re.sub(r"^(b[uú]squeda final|query|search query|b[uú]squeda)\s*:\s*", "", text, flags=re.I)
    text = text.strip(" \"'`.,;:-")

    if not text:
        return ""
    if "__open_ended__" in text:
        return ""
    if is_sentinel_query(text):
        return ""
    if len(text) > 100:
        return ""
    if "http://" in text or "https://" in text:
        return ""

    return text


def _expand_topic(topic: str, target: str) -> str:
    topic = normalize_text(topic)

    for keywords, mapping in INTEREST_QUERY_MAP:
        if any(k in topic for k in keywords):
            return mapping.get(target) or mapping.get("auto") or topic

    if target == "youtube":
        return f"{topic} interesante"

    return f"{topic} interesante"


def _query_from_context(context: str, target: str) -> str:
    if not context:
        return ""

    scored: list[tuple[int, str]] = []

    for keywords, mapping in INTEREST_QUERY_MAP:
        score = sum(1 for k in keywords if k in context)
        if score:
            query = mapping.get(target) or mapping.get("auto") or ""
            if query:
                scored.append((score, query))

    if not scored:
        return ""

    scored.sort(reverse=True, key=lambda item: item[0])
    return scored[0][1]
