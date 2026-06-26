from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from agent.memory.learning_memory import normalize_phrase
from agent.models.model_settings import get_main_model
from agent.models.ollama_client import OllamaClient


@dataclass(frozen=True)
class MemoryIntentClassification:
    should_save: bool
    memory_type: str = "instruction"
    key: str | None = None
    value: str = ""
    confidence: float = 0.0
    reason: str = ""


SAFE_MEMORY_TYPES = {
    "instruction",
    "preference",
    "project",
    "alias",
    "personal_fact",
}


NEGATIVE_ACTION_MARKERS = {
    "abre",
    "abrir",
    "open",
    "busca",
    "buscar",
    "investiga",
    "ejecuta",
    "mueve",
    "click",
    "haz click",
    "escribe",
    "borra",
    "elimina",
    "instala",
}


def classify_memory_intent(
    text: str,
    *,
    client: OllamaClient | None = None,
    model: str | None = None,
) -> MemoryIntentClassification:
    raw = (text or "").strip()
    if not raw:
        return MemoryIntentClassification(False, reason="empty")

    normalized = normalize_phrase(raw)

    # Guardrail rápido: comandos claros no son memoria.
    if any(normalized.startswith(marker + " ") for marker in NEGATIVE_ACTION_MARKERS):
        return MemoryIntentClassification(False, reason="looks_like_action")

    # Señales semánticas fuertes sin modelo, para ahorrar latencia.
    heuristic = _classify_with_semantic_patterns(raw)
    if heuristic is not None:
        return heuristic

    # Si no hay ninguna señal de futuro/memoria, no gastes modelo.
    if not _has_soft_memory_signal(normalized):
        return MemoryIntentClassification(False, reason="no_memory_signal")

    return _classify_with_model(raw, client=client, model=model)


def _classify_with_semantic_patterns(text: str) -> MemoryIntentClassification | None:
    patterns: list[tuple[str, str]] = [
        (r"^\s*quiero\s+que\s+sepas\s+que\s+(.+?)\s*$", "instruction"),
        (r"^\s*para\s+futuras?\s+conversaciones?\s*,?\s+(.+?)\s*$", "instruction"),
        (r"^\s*para\s+la\s+pr[oó]xima\s+vez\s*,?\s+(.+?)\s*$", "instruction"),
        (r"^\s*no\s+olvides\s+que\s+(.+?)\s*$", "instruction"),
        (r"^\s*ten\s+esto\s+presente\s*:?\s+(.+?)\s*$", "instruction"),
        (r"^\s*tenlo\s+presente\s*:?\s+(.+?)\s*$", "instruction"),
        (r"^\s*importante\s*:?\s+(.+?)\s*$", "instruction"),
    ]

    for pattern, fallback_type in patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue

        value = match.group(1).strip()
        if not value:
            return None

        memory_type = _classify_memory_type(value, fallback=fallback_type)
        return MemoryIntentClassification(
            should_save=True,
            memory_type=memory_type,
            key=_guess_key(value),
            value=value,
            confidence=0.88,
            reason="semantic_pattern",
        )

    return None


def _has_soft_memory_signal(normalized: str) -> bool:
    signals = (
        "quiero que sepas",
        "para futuras conversaciones",
        "para futura conversacion",
        "para la proxima vez",
        "no olvides",
        "ten esto presente",
        "tenlo presente",
        "a partir de ahora",
        "de ahora en adelante",
        "cuando hablemos",
        "en el futuro",
    )
    return any(signal in normalized for signal in signals)


def _classify_with_model(
    text: str,
    *,
    client: OllamaClient | None = None,
    model: str | None = None,
) -> MemoryIntentClassification:
    selected_model = model or get_main_model()
    ollama_client = client or OllamaClient()

    messages = _messages(text)

    try:
        raw = ollama_client.chat(
            selected_model,
            messages,
            think=False,
            options={
                "temperature": 0,
                "num_predict": 160,
            },
        )
    except Exception as exc:
        return MemoryIntentClassification(False, reason=f"model_error:{exc}")

    data = _parse_json(raw)
    if not data:
        return MemoryIntentClassification(False, reason="invalid_json")

    should_save = bool(data.get("should_save"))
    value = str(data.get("value") or "").strip()
    memory_type = str(data.get("memory_type") or "instruction").strip()
    key = data.get("key")
    confidence = _safe_float(data.get("confidence"), default=0.0)
    reason = str(data.get("reason") or "model").strip()

    if memory_type not in SAFE_MEMORY_TYPES:
        memory_type = "instruction"

    if not should_save:
        return MemoryIntentClassification(False, reason=reason, confidence=confidence)

    if confidence < 0.80:
        return MemoryIntentClassification(False, reason=f"low_confidence:{confidence}", confidence=confidence)

    if not value:
        return MemoryIntentClassification(False, reason="empty_value", confidence=confidence)

    return MemoryIntentClassification(
        should_save=True,
        memory_type=memory_type,
        key=str(key).strip() if key else None,
        value=value,
        confidence=confidence,
        reason=reason,
    )


def _messages(text: str) -> list[dict[str, str]]:
    system = """Eres un clasificador de memoria para un agente local llamado Tuli.

Tu única tarea es decidir si el usuario está pidiendo guardar una memoria explícita para futuras conversaciones.

Responde SOLO JSON válido. No expliques.

Schema:
{
  "should_save": true|false,
  "memory_type": "instruction|preference|project|alias|personal_fact",
  "key": string|null,
  "value": string,
  "confidence": number,
  "reason": string
}

Reglas:
- Guarda si el usuario pide explícitamente que el agente sepa, recuerde, no olvide o use algo en el futuro.
- Guarda preferencias estables, alias, datos del proyecto, instrucciones futuras y hechos personales dados con intención de memoria.
- NO guardes comentarios casuales.
- NO guardes acciones como abrir apps, buscar, hacer click, escribir o mover ventanas.
- NO guardes estados temporales como "hoy estoy cansado".
- Si hay duda, should_save=false.
- value debe ser solo la memoria útil, sin frases como "quiero que sepas que".
"""

    user = f"""Mensaje del usuario:
{text}

JSON:"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _parse_json(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None

    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return None

    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _safe_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _classify_memory_type(value: str, *, fallback: str = "instruction") -> str:
    normalized = normalize_phrase(value)

    if "cuando diga" in normalized or "cuando yo diga" in normalized:
        return "alias"

    if (
        "prefiero" in normalized
        or "me gusta que" in normalized
        or "no me gusta que" in normalized
        or "no vuelvas a" in normalized
    ):
        return "preference"

    if (
        "proyecto" in normalized
        or "agente" in normalized
        or "tuli" in normalized
        or "cliente" in normalized
    ):
        return "project"

    if (
        "mi cumpleaños" in normalized
        or "mi cumpleanos" in normalized
        or "mi color favorito" in normalized
        or "mi nombre" in normalized
    ):
        return "personal_fact"

    return fallback


def _guess_key(value: str) -> str | None:
    normalized = normalize_phrase(value)

    alias_match = re.search(
        r"cuando\s+(?:yo\s+)?diga\s+(.+?)\s+(?:me\s+refiero\s+a|significa|quiere\s+decir)\s+(.+)",
        normalized,
    )
    if alias_match:
        return alias_match.group(1).strip()

    if "mi cumpleaños" in normalized or "mi cumpleanos" in normalized:
        return "birthday"

    if "mi color favorito" in normalized:
        return "favorite_color"

    if "no vuelvas a" in normalized:
        return "negative_preference"

    if "prefiero" in normalized:
        return "preference"

    return None
