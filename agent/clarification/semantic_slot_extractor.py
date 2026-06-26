from __future__ import annotations

import re
import json
import subprocess
from dataclasses import dataclass


LLM_SLOT_EXTRACTOR_MODEL = "qwen3-0.6b-ud-q8-k-xl-local:latest"
LLM_SLOT_EXTRACTOR_TIMEOUT_SECONDS = 8


@dataclass(slots=True)
class SlotExtraction:
    value: str | None
    confidence: str
    reason: str


_STOP_PREFIX_RE = re.compile(
    r"""
    ^\s*
    (?:
        si|sí|claro|dale|ok|okay|perfecto|correcto|exacto|bueno|
        por\s+favor|please|
        puedes|puede|podrias|podrías|quiero|quisiera|me\s+gustaria|me\s+gustaría|
        hazlo|hacerlo|intenta|vamos\s+a|dale\s+con
    )
    \b
    [\s,.:;!-]*
    """,
    re.I | re.X,
)

_ACTION_WORD_RE = re.compile(
    r"""
    \b
    (?:
        abre|abrir|ábreme|abreme|abrirlo|ábrelo|abrelo|
        busca|buscar|búscame|buscame|investiga|investigar|consulta|consultar|
        llévame|llevame|muéstrame|muestrame|muestra|ir\s+a|ve\s+a|
        usa|usar|hazlo\s+con|hacerlo\s+con|con
    )
    \b
    """,
    re.I | re.X,
)

_SLOT_NOUN_RE = re.compile(
    r"""
    \b
    (?:
        app|aplicacion|aplicación|programa|
        pagina|página|sitio|web|url|
        busqueda|búsqueda|tema|cosa
    )
    \b
    """,
    re.I | re.X,
)

_DOMAIN_RE = re.compile(
    r"\b(?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s]*)?\b",
    re.I,
)

_KNOWN_ENTITY_RE = re.compile(
    r"\b("
    r"safari|chrome|google chrome|firefox|terminal|finder|calculadora|calculator|"
    r"notas|notes|canva|github|openai|youtube|google|ollama|chatgpt|whatsapp|telegram|"
    r"discord|slack|spotify|figma|photoshop|illustrator|premiere|after effects|"
    r"vscode|visual studio code|xcode"
    r")\b",
    re.I,
)


def extract_slot_value(user_text: str, pending: str | None) -> SlotExtraction:
    """
    Extrae el dato útil desde una respuesta natural a una aclaración.

    Flujo híbrido:
    1. Reglas rápidas para casos obvios.
    2. Si no hay valor claro, fallback LLM pequeño en JSON.
    """
    deterministic = _extract_slot_value_deterministic(user_text, pending)

    # HIGH = caso obvio, no gastes LLM.
    if deterministic.confidence == "high" and deterministic.value:
        return deterministic

    # MEDIUM/LOW = validar con LLM pequeño. Esto evita ejecutar frases completas
    # como "umm me refiero a ollama" o "no mejor dime un chiste".
    llm = _extract_slot_value_with_llm(user_text, pending)
    if llm.confidence in {"high", "medium"} and llm.value:
        return llm

    return deterministic


def _extract_slot_value_deterministic(user_text: str, pending: str | None) -> SlotExtraction:
    original = (user_text or "").strip()
    if not original:
        return SlotExtraction(None, "none", "empty")

    text = _normalize_spaces(original)

    if _is_topic_change(text):
        return SlotExtraction(None, "high", "topic_change")

    if _is_only_confirmation(text):
        return SlotExtraction(None, "none", "confirmation_without_value")

    # 1) URL o dominio explícito: máxima confianza.
    domain = _DOMAIN_RE.search(text)
    if domain and pending in {"target_url", "resolved_reference_confirmation", "search_query", "ambiguous_reference"}:
        return SlotExtraction(_clean_value(domain.group(0)), "high", "explicit_domain_or_url")

    # 2) Entidad conocida: esto cubre lenguaje natural sin quedarse con toda la frase.
    entity = _last_known_entity(text)
    if entity:
        if pending == "target_app":
            return SlotExtraction(entity, "high", "known_app_entity")
        if pending in {"target_url", "resolved_reference_confirmation"}:
            return SlotExtraction(entity, "high", "known_site_entity")
        if pending in {"search_query", "ambiguous_reference"}:
            if re.search(r"\b(me\s+refiero\s+a|refiero\s+a|hablo\s+de|sobre)\b", text, re.I):
                return SlotExtraction(entity, "high", "known_entity_search_reference")
            compact = _extract_after_action(text, pending)
            return SlotExtraction(compact or entity, "medium", "known_entity_search")

    # 3) Extraer lo que venga después de una acción natural.
    after_action = _extract_after_action(text, pending)
    if after_action:
        return SlotExtraction(after_action, "medium", "after_action_phrase")

    # 4) Si no hay acción, pero el texto parece un valor directo, usarlo.
    direct = _clean_direct_value(text, pending)
    if direct:
        return SlotExtraction(direct, "medium", "direct_free_text_value")

    return SlotExtraction(None, "low", "no_slot_value_found")



def _extract_slot_value_with_llm(user_text: str, pending: str | None) -> SlotExtraction:
    if not pending:
        return SlotExtraction(None, "low", "no_pending_for_llm")

    prompt = f"""
Eres un extractor semántico para un agente local.

Tarea:
Dado un pending_clarification y la respuesta del usuario, extrae SOLO el valor útil que completa el slot pendiente.

No respondas explicación.
No uses markdown.
No inventes.
Responde SOLO JSON válido.

pending_clarification:
{pending}

Respuesta del usuario:
{user_text}

Slots:
- target_app: extrae el nombre de la aplicación.
- target_url: extrae el sitio, dominio, nombre de página o URL.
- resolved_reference_confirmation: extrae el sitio, dominio, nombre de página o URL.
- search_query: extrae el tema exacto a buscar.
- ambiguous_reference: extrae el referente útil.

Reglas:
- Si el usuario solo confirma sin dar valor, value debe ser null.
- Si el usuario cambia de tema, is_answer_to_pending debe ser false.
- Si dice algo como "umm me refiero a ollama", value debe ser "ollama".
- Si dice "puedes abrir github", value debe ser "github".
- Si dice "quiero que sea canva", value debe ser "canva".
- Si dice "sí, busca documentación de ollama", value debe ser "documentación de ollama".

Formato exacto:
{{"is_answer_to_pending": true, "value": "texto o null", "confidence": "high|medium|low", "reason": "breve"}}
""".strip()

    try:
        completed = subprocess.run(
            ["ollama", "run", LLM_SLOT_EXTRACTOR_MODEL, prompt],
            capture_output=True,
            text=True,
            timeout=LLM_SLOT_EXTRACTOR_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        return SlotExtraction(None, "low", f"llm_extractor_error:{type(exc).__name__}")

    raw = (completed.stdout or "").strip()
    if not raw:
        return SlotExtraction(None, "low", "llm_empty_output")

    data = _parse_json_object(raw)
    if not data:
        return SlotExtraction(None, "low", "llm_invalid_json")

    if data.get("is_answer_to_pending") is False:
        return SlotExtraction(None, "low", "llm_topic_change")

    value = data.get("value")
    if value is None:
        return SlotExtraction(None, str(data.get("confidence") or "low"), "llm_null_value")

    value = _clean_value(str(value))
    if not value:
        return SlotExtraction(None, str(data.get("confidence") or "low"), "llm_empty_value")

    confidence = str(data.get("confidence") or "medium").lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"

    return SlotExtraction(value, confidence, f"llm:{data.get('reason') or 'slot_extracted'}")


def _parse_json_object(raw: str) -> dict | None:
    text = raw.strip()

    # Algunos modelos pequeños pueden envolver JSON en texto o thinking.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    text = text[start : end + 1]

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    return parsed


def _is_topic_change(text: str) -> bool:
    compact = _normalize_spaces(text).lower().strip(" .,:;!?¿¡")
    return bool(
        re.search(
            r"\b(no\s+mejor|mejor|olvidalo|olvídalo|cambia|cambiemos|otra\s+cosa|dime\s+un\s+chiste)\b",
            compact,
            re.I,
        )
    )

def _normalize_spaces(text: str) -> str:
    return " ".join(text.strip().split())


def _is_only_confirmation(text: str) -> bool:
    normalized = _normalize_spaces(text).lower().strip(" .,:;!?¿¡")
    return normalized in {
        "si",
        "sí",
        "claro",
        "dale",
        "ok",
        "okay",
        "perfecto",
        "correcto",
        "exacto",
    }


def _last_known_entity(text: str) -> str | None:
    matches = list(_KNOWN_ENTITY_RE.finditer(text))
    if not matches:
        return None
    return _clean_value(matches[-1].group(1))


def _extract_after_action(text: str, pending: str | None) -> str | None:
    cleaned = text.strip()

    # Quita prefijos conversacionales repetidos sin depender de una frase exacta.
    last = None
    while cleaned != last:
        last = cleaned
        cleaned = _STOP_PREFIX_RE.sub("", cleaned).strip()

    # Busca la última acción dentro de la frase y toma lo que queda después.
    matches = list(_ACTION_WORD_RE.finditer(cleaned))
    if matches:
        cleaned = cleaned[matches[-1].end():].strip()

    # Quita conectores típicos después de la acción.
    cleaned = re.sub(
        r"^\s*(?:a|el|la|los|las|un|una|sobre|acerca\s+de|informacion\s+de|información\s+de|informacion\s+sobre|información\s+sobre)\s+",
        "",
        cleaned,
        flags=re.I,
    ).strip()

    cleaned = _remove_slot_nouns(cleaned, pending)
    cleaned = _clean_value(cleaned)

    if not cleaned:
        return None

    if _looks_like_command_without_value(cleaned):
        return None

    return cleaned


def _clean_direct_value(text: str, pending: str | None) -> str | None:
    cleaned = text.strip()

    # Si es una frase larga con verbos pero no pudimos extraer valor,
    # no la uses completa como app/query/url.
    if len(cleaned.split()) > 5 and _ACTION_WORD_RE.search(cleaned):
        return None

    cleaned = _remove_slot_nouns(cleaned, pending)
    cleaned = _clean_value(cleaned)

    if not cleaned:
        return None

    if pending == "target_app" and len(cleaned.split()) > 4:
        return None

    return cleaned


def _remove_slot_nouns(text: str, pending: str | None) -> str:
    cleaned = text.strip()

    if pending == "target_app":
        cleaned = re.sub(r"^\s*(?:app|aplicacion|aplicación|programa)\s+", "", cleaned, flags=re.I)

    if pending in {"target_url", "resolved_reference_confirmation"}:
        cleaned = re.sub(r"^\s*(?:pagina|página|sitio|web|url)\s+", "", cleaned, flags=re.I)

    if pending in {"search_query", "ambiguous_reference"}:
        cleaned = re.sub(r"^\s*(?:tema|busqueda|búsqueda|informacion|información)\s+", "", cleaned, flags=re.I)

    # Si quedó solo el nombre del slot, no hay valor.
    if _SLOT_NOUN_RE.fullmatch(cleaned.strip()):
        return ""

    return cleaned


def _looks_like_command_without_value(text: str) -> bool:
    compact = text.lower().strip(" .,:;!?¿¡")
    return compact in {
        "abre",
        "abrir",
        "busca",
        "buscar",
        "investiga",
        "consulta",
        "hazlo",
        "hacerlo",
        "puedes",
        "quiero",
    }


def _clean_value(text: str) -> str:
    cleaned = text.strip().strip(" .,:;!?¿¡")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned
