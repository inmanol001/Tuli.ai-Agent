from __future__ import annotations

import re
import json
from typing import Any

from agent.capabilities.tools.browser_tools import KNOWN_SITE_URLS, normalize_http_url
from agent.capabilities.tools.schemas import ToolCall


OPEN_INTENT_PATTERNS = (
    "abre",
    "abrir",
    "open",
    "quiero ver",
    "ver el sitio",
    "ver sitio",
    "mostrar",
    "muestra",
    "muéstrame",
    "muestrame",
    "navega",
    "navegar",
    "visita",
    "visit",
    "ir a",
    "ir al",
    "ir a la",
    "sitio de",
    "website de",
    "web de",
)

ABSOLUTE_URL_RE = re.compile(r"https?://[^\s)>,]+", re.I)
BARE_DOMAIN_RE = re.compile(
    r"\b(?:[a-z0-9-]+\.)+(?:[a-z]{2,})(?:/[^\s)>,]*)?\b",
    re.I,
)


def _normalized_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _has_open_intent(text: str) -> bool:
    normalized = _normalized_text(text)
    return any(pattern in normalized for pattern in OPEN_INTENT_PATTERNS)


def _selected_browser_tool_names(selected_tools: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for tool in selected_tools or []:
        if isinstance(tool, dict):
            name = tool.get("name")
        else:
            name = getattr(tool, "name", None)
        if isinstance(name, str) and name:
            names.add(name)
    return names


def _extract_known_destination(text: str) -> str | None:
    normalized = _normalized_text(text)
    domain_match = BARE_DOMAIN_RE.search(text or "")
    if domain_match:
        domain = domain_match.group(0).strip().lower().rstrip(".,)")
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    for site_name in KNOWN_SITE_URLS:
        if site_name in normalized:
            return site_name
    return None


def fallback_browser_search_call(
    user_text: str, selected_tools: list[dict[str, Any]]
) -> tuple[ToolCall, str] | None:
    if "browser_search" not in _selected_browser_tool_names(selected_tools):
        return None

    if not _has_open_intent(user_text):
        absolute_url = ABSOLUTE_URL_RE.search(user_text or "")
        if absolute_url is None:
            return None
    else:
        absolute_url = ABSOLUTE_URL_RE.search(user_text or "")

    if absolute_url is not None:
        url = normalize_http_url(absolute_url.group(0))
        return (
            ToolCall(
                tool_name="browser_search",
                arguments={"query": url, "target": "url"},
                risk_level="low",
                requires_confirmation=False,
            ),
            "browser_search_direct_url",
        )

    destination = _extract_known_destination(user_text)
    if not destination:
        return None

    fallback_kind = (
        "browser_search_known_destination"
        if destination in KNOWN_SITE_URLS
        else "browser_search_domain"
    )
    return (
        ToolCall(
            tool_name="browser_search",
            arguments={"query": destination, "target": "auto"},
            risk_level="low",
            requires_confirmation=False,
        ),
        fallback_kind,
    )


def fallback_action_guard_call(action_debug: dict[str, Any]) -> tuple[ToolCall, str] | None:
    """
    Fallback determinístico cuando ActionIntentGuard recuperó una acción explícita,
    pero ToolPlanner no emitió tool_call nativa.

    No llama modelos.
    No ejecuta tools.
    Solo construye una ToolCall compatible con el executor.
    """
    if not isinstance(action_debug, dict):
        return None

    if action_debug.get("action_guard_recovered") is not True:
        return None

    intent = action_debug.get("action_intent_guard") or {}
    if not isinstance(intent, dict):
        return None

    if intent.get("action_required") is not True:
        return None

    action_type = (intent.get("action_type") or "").strip().lower()
    target = (intent.get("target") or "").strip()

    if not action_type or not target:
        return None

    if action_type == "open":
        return (
            ToolCall(
                tool_name="open_app",
                arguments={"app_name": target},
                risk_level="low",
                requires_confirmation=False,
            ),
            "action_guard_open_app",
        )

    if action_type == "show":
        return (
            ToolCall(
                tool_name="browser_search",
                arguments={"query": target, "target": "auto"},
                risk_level="low",
                requires_confirmation=False,
            ),
            "action_guard_browser_search",
        )

    if action_type == "search":
        return (
            ToolCall(
                tool_name="web_search",
                arguments={"query": target, "max_results": 5},
                risk_level="low",
                requires_confirmation=False,
            ),
            "action_guard_web_search",
        )

    if action_type == "activate":
        normalized_target = _normalized_text(target)
        if "mission control" in normalized_target or "mision control" in normalized_target:
            return (
                ToolCall(
                    tool_name="macos_space_mission_control",
                    arguments={},
                    risk_level="low",
                    requires_confirmation=False,
                ),
                "action_guard_mission_control",
            )
        return (
            ToolCall(
                tool_name="open_app",
                arguments={"app_name": target},
                risk_level="low",
                requires_confirmation=False,
            ),
            "action_guard_activate_open_app",
        )

    if action_type == "window_move":
        action = _window_action_from_target(target)
        if not action:
            return None
        return (
            ToolCall(
                tool_name="window_native_tiling",
                arguments={"action": action},
                risk_level="low",
                requires_confirmation=False,
            ),
            f"action_guard_window_{action}",
        )

    return None


def _window_action_from_target(target: str) -> str | None:
    text = _normalized_text(target)

    if "izquierda" in text or "left" in text:
        return "left"
    if "derecha" in text or "right" in text:
        return "right"
    if "centro" in text or "centr" in text or "center" in text:
        return "center"
    if (
        "llene" in text
        or "llenar" in text
        or "llena" in text
        or "pantalla completa" in text
        or "maximiza" in text
        or "maximizar" in text
        or "fill" in text
        or "fullscreen" in text
    ):
        return "fill"
    if "arriba" in text or "top" in text:
        return "top"
    if "abajo" in text or "bottom" in text:
        return "bottom"
    if "volver" in text or "anterior" in text or "return" in text:
        return "return"

    return None



# ---------------------------------------------------------------------------
# Web result reference fallback
# ---------------------------------------------------------------------------

_WEB_RESULT_ORDINALS = {
    "primer": 0, "primero": 0, "primera": 0, "uno": 0,
    "segundo": 1, "segunda": 1, "dos": 1,
    "tercero": 2, "tercer": 2, "tercera": 2, "tres": 2,
    "cuarto": 3, "cuarta": 3, "cuatro": 3,
    "quinto": 4, "quinta": 4, "cinco": 4,
    "sexto": 5, "sexta": 5, "seis": 5,
    "septimo": 6, "séptimo": 6, "septima": 6, "séptima": 6, "siete": 6,
    "octavo": 7, "octava": 7, "ocho": 7,
    "noveno": 8, "novena": 8, "nueve": 8,
    "decimo": 9, "décimo": 9, "decima": 9, "décima": 9, "diez": 9,
}



def _is_vague_recent_site_request(text: str) -> bool:
    lowered = _normalized_text(text)
    has_open = re.search(
        r"\b(abre|abrir|ábreme|abreme|muestra|muéstrame|muestrame|llévame|llevame|entra|ve|ir)\b",
        lowered,
        re.I,
    )
    has_vague_ref = re.search(
        r"\b(eso|esto|ese sitio|esa pagina|esa página|ese link|ese enlace|ahi|ahí|alli|allí)\b",
        lowered,
        re.I,
    )
    return bool(has_open and has_vague_ref)


def _recent_tool_payloads_from_context(context):
    for turn in reversed(getattr(context, "recent_history", []) or []):
        if getattr(turn, "role", None) != "tool":
            continue
        content = getattr(turn, "content", "") or ""
        try:
            payload = json.loads(content)
        except Exception:
            continue
        if isinstance(payload, dict):
            yield payload


def _get_last_web_reference_from_context(context) -> str | None:
    """
    Devuelve el mejor target reciente para abrir cuando el usuario dice
    "ese sitio" sin ordinal.

    Preferencia:
    1. query del último web_search, porque browser_search(query, auto)
       puede mapear Ollama -> ollama.com, Canva -> canva.com, etc.
    2. url del último browser_search.
    3. url/title del primer resultado de último web_search si no hay query.
    """
    # Primero revisar tool turns reales del historial.
    for payload in _recent_tool_payloads_from_context(context):
        tool_name = payload.get("tool_name")
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            continue

        if tool_name == "web_search":
            query = (data.get("query") or "").strip()
            if query:
                return query

            results = data.get("results") or []
            if isinstance(results, list) and results:
                best = _pick_best_web_result(results)
                if best:
                    return best

        if tool_name == "browser_search":
            url = (data.get("url") or "").strip()
            query = (data.get("query") or "").strip()
            if url:
                return url
            if query:
                return query

    # Fallback viejo: conversation_state si existe.
    session_state = getattr(context, "session_state", None) or {}
    conversation_state = session_state.get("conversation_state") or {}
    if isinstance(conversation_state, dict):
        last = conversation_state.get("last") or {}
        if isinstance(last, dict):
            query = (last.get("web_query") or last.get("query") or "").strip()
            if query:
                return query

    return None


def _pick_best_web_result(results: list) -> str | None:
    if not isinstance(results, list):
        return None

    # Preferir dominios oficiales si el título coincide con dominio/proyecto.
    for result in results[:5]:
        if not isinstance(result, dict):
            continue
        title = str(result.get("title") or "").lower()
        url = str(result.get("url") or result.get("link") or "").strip()
        if not url:
            continue
        clean_url = url.lower()
        if "wikipedia.org" in clean_url:
            continue
        if title and any(token in clean_url for token in title.replace("-", " ").split()[:2]):
            return url

    for result in results[:5]:
        if not isinstance(result, dict):
            continue
        url = str(result.get("url") or result.get("link") or "").strip()
        if url:
            return url

    return None


def fallback_web_result_reference_call(context):
    import re
    from agent.capabilities.tools.schemas import ToolCall

    user_text = getattr(context, "user_message", "") or ""
    lowered = user_text.lower().strip()
    if not lowered:
        return None

    explicit_result_reference = re.search(
        r"\b("
        r"abre|abrir|ábreme|abreme|muestra|muéstrame|muestrame|"
        r"enséñame|ensename|llévame|llevame|entra|ve|ir"
        r")\b\s+(?:el|la|al|a\s+el|a\s+la)?\s*"
        r"("
        r"primer|primero|primera|segundo|segunda|tercero|tercer|tercera|"
        r"cuarto|cuarta|quinto|quinta|sexto|sexta|septimo|séptimo|"
        r"septima|séptima|octavo|octava|noveno|novena|decimo|décimo|"
        r"uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|#?\d+"
        r")\b",
        lowered,
    )

    openish = re.search(
        r"\b(abre|abrir|ábreme|abreme|muestra|muéstrame|muestrame|"
        r"enséñame|ensename|llévame|llevame|entra|ve|ir)\b",
        lowered,
    )
    resultish = re.search(
        r"\b(resultado|link|enlace|página|pagina|web|sitio|"
        r"primero|primer|primera|segundo|segunda|tercero|tercer|tercera|"
        r"cuarto|cuarta|quinto|quinta|sexto|sexta|septimo|séptimo|"
        r"octavo|octava|noveno|novena|decimo|décimo|"
        r"uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|#\d+|\d+)\b",
        lowered,
    )

    if not explicit_result_reference and (not openish or not resultish):
        return None

    index = _extract_web_result_index(lowered)
    if index is None:
        if _is_vague_recent_site_request(lowered):
            recent_target = _get_last_web_reference_from_context(context)
            if recent_target:
                return (
                    ToolCall(
                        tool_name="browser_search",
                        arguments={"query": str(recent_target), "target": "auto"},
                        risk_level="low",
                        requires_confirmation=False,
                    ),
                    "browser_search_recent_web_reference",
                )
        return None

    web_results = _get_last_web_results_from_context(context)
    if not web_results or index < 0 or index >= len(web_results):
        return None

    result = web_results[index]
    if not isinstance(result, dict):
        return None

    url = result.get("url") or result.get("link") or result.get("href") or result.get("source_url")
    if not url:
        return None

    tool_call = ToolCall(
        tool_name="browser_search",
        arguments={"query": str(url), "target": "url"},
        risk_level="low",
        requires_confirmation=False,
    )
    return tool_call, "browser_search_last_web_result"


def _extract_web_result_index(text):
    import re

    numbered = re.search(
        r"\b(?:resultado|link|enlace|página|pagina|web|sitio)\s*"
        r"(?:n[uú]mero\s*)?(?:#\s*)?(\d{1,2})\b",
        text,
    )
    if numbered:
        return int(numbered.group(1)) - 1

    hashed = re.search(r"#\s*(\d{1,2})\b", text)
    if hashed:
        return int(hashed.group(1)) - 1

    short_number = re.search(r"\b(?:al|el|la|los|las)\s+(\d{1,2})\b", text)
    if short_number:
        return int(short_number.group(1)) - 1

    for word, index in _WEB_RESULT_ORDINALS.items():
        if re.search(rf"\b{re.escape(word)}\b", text):
            return index

    return None


def _get_last_web_results_from_context(context):
    session_state = getattr(context, "session_state", None) or {}
    if not isinstance(session_state, dict):
        return []

    conversation_state = session_state.get("conversation_state") or {}
    if not isinstance(conversation_state, dict):
        return []

    last = conversation_state.get("last") or {}
    if not isinstance(last, dict):
        return []

    web_results = (
        last.get("web_results")
        or last.get("last_web_results")
        or conversation_state.get("last_web_results")
        or []
    )

    if not isinstance(web_results, list):
        return []

    return web_results
