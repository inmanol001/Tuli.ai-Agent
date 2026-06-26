from __future__ import annotations

import re
from typing import Any

from agent.capabilities.tools.browser_tools import normalize_http_url
from agent.capabilities.tools.schemas import ToolCall
from agent.gateway.message_types import ContextPackage
from agent.clarification.semantic_slot_extractor import extract_slot_value


_CANCEL_RE = re.compile(r"^\s*(cancel|cancela|cancelar|no|olvidalo|olvídalo)\s*[!.?]*\s*$", re.I)
_YES_RE = re.compile(r"^\s*(s[ií]|si|sí|ok|dale|hazlo|adelante|correcto|exacto)\s*[!.?]*\s*$", re.I)
_URL_RE = re.compile(r"https?://[^\s)>,.]+(?:\.[^\s)>,.]+)*[^\s)>,.]*", re.I)
_VAGUE_RE = re.compile(
    r"^\s*(eso|esto|esa|ese|esta|este|lo ultimo|lo último|el ultimo|el último|la ultima|la última)\s*$",
    re.I,
)
_OPERATIONAL_NEW_REQUEST_RE = re.compile(
    r"\b("
    r"abre|abrir|busca|buscar|investiga|consulta|mueve|mover|acomoda|centra|"
    r"haz|hacer|crea|crear|diseña|diseñar|edita|editar|quiero\s+editar|quiero\s+crear|quiero\s+hacer"
    r")\b",
    re.I,
)
_APPISH_RE = re.compile(r"^[A-Za-zÁÉÍÓÚÑáéíóúñ0-9 ._-]{2,40}$")
_NON_EXECUTABLE_OPTION_RE = re.compile(
    r"\b("
    r"escribirme|escribir|dime|dar\s+m[aá]s\s+contexto|"
    r"buscar\s+el\s+sitio\s+por\s+nombre|listar\s+apps|"
    r"otro\s+tema|otra\s+cosa|otro\s+destino|cancelar"
    r")\b",
    re.I,
)


def pending_clarification_tool_call(context: ContextPackage) -> tuple[ToolCall, str] | None:
    pending = context.session_state.get("pending_clarification")
    inferred_pending = _infer_pending_from_last_assistant(context)
    if inferred_pending and pending != inferred_pending:
        pending = inferred_pending

    user_text = context.user_message or ""
    normalized = _normalized(user_text)
    selected_tools = _selected_tool_names(context.selected_tools)

    if not pending or _CANCEL_RE.match(user_text):
        return None

    choice = _choice(user_text)
    last_options = _last_assistant_options(context)
    selected_label = _selected_option_label(choice, last_options)
    original_user_intent = _previous_user_intent(context)

    if pending == "window_action":
        # Para window_action, la elección numérica manda.
        # No uses selected_label porque el builder puede haber mostrado candidatos
        # contaminados del historial como URLs.
        action = _resolve_window_action(normalized, None)
        if action is None:
            action = _resolve_window_action(normalized, selected_label)
        if not action or "window_native_tiling" not in selected_tools:
            return None
        return (
            ToolCall(
                tool_name="window_native_tiling",
                arguments={"action": action},
                risk_level="low",
                requires_confirmation=False,
            ),
            f"pending_window_action_{action}",
        )

    if pending in {"target_url", "resolved_reference_confirmation"}:
        target_text = _target_text_from_reply(user_text, selected_label, last_options, pending)
        if not target_text or _VAGUE_RE.match(target_text) or choice in {"1", "2", "3"} and not selected_label:
            return None
        if "browser_search" not in selected_tools:
            return None
        return _browser_call(target_text, "pending_target_url")

    if pending == "search_query":
        query = _target_text_from_reply(user_text, selected_label, last_options, pending)
        if not query or _VAGUE_RE.match(query):
            return None
        if "web_search" not in selected_tools:
            return None
        return (
            ToolCall(
                tool_name="web_search",
                arguments={"query": query, "max_results": 5},
                risk_level="low",
                requires_confirmation=False,
            ),
            "pending_search_query",
        )

    if pending == "ambiguous_reference":
        target_text = _target_text_from_reply(user_text, selected_label, last_options, pending)
        if not target_text or _VAGUE_RE.match(target_text):
            return None

        if _intent_wants_open(original_user_intent) and "browser_search" in selected_tools:
            return _browser_call(target_text, "pending_ambiguous_open")

        if _intent_wants_search(original_user_intent) and "web_search" in selected_tools:
            return (
                ToolCall(
                    tool_name="web_search",
                    arguments={"query": target_text, "max_results": 5},
                    risk_level="low",
                    requires_confirmation=False,
                ),
                "pending_ambiguous_search",
            )

        if _looks_like_url_or_domain(target_text) and "browser_search" in selected_tools:
            return _browser_call(target_text, "pending_ambiguous_url")

        if "web_search" in selected_tools:
            return (
                ToolCall(
                    tool_name="web_search",
                    arguments={"query": target_text, "max_results": 5},
                    risk_level="low",
                    requires_confirmation=False,
                ),
                "pending_ambiguous_search_default",
            )

    if pending == "target_app":
        app_name = _target_text_from_reply(user_text, selected_label, last_options, pending)
        if not app_name or _VAGUE_RE.match(app_name):
            return None
        if _looks_like_new_request(app_name):
            return None
        if _looks_like_url_or_domain(app_name):
            return None
        if not _looks_like_app_name(app_name):
            return None
        if "open_app" not in selected_tools:
            return None
        return (
            ToolCall(
                tool_name="open_app",
                arguments={"app_name": app_name},
                risk_level="low",
                requires_confirmation=False,
            ),
            "pending_target_app",
        )

    return None


def _browser_call(target_text: str, reason: str) -> tuple[ToolCall, str]:
    target_text = target_text.strip()
    match = _URL_RE.search(target_text)
    if match:
        query = normalize_http_url(match.group(0))
        target = "url"
    else:
        query = _strip_action_prefix(target_text)
        target = "auto"
    return (
        ToolCall(
            tool_name="browser_search",
            arguments={"query": query, "target": target},
            risk_level="low",
            requires_confirmation=False,
        ),
        reason,
    )


def _target_text_from_reply(
    user_text: str,
    selected_label: str | None,
    options: dict[str, str],
    pending: str | None = None,
) -> str | None:
    if selected_label:
        cleaned_label = _clean_option_label(selected_label)
        if _NON_EXECUTABLE_OPTION_RE.search(cleaned_label):
            return None
        return cleaned_label

    if _YES_RE.match(user_text):
        if len(options) == 1:
            cleaned_label = _clean_option_label(next(iter(options.values())))
            if _NON_EXECUTABLE_OPTION_RE.search(cleaned_label):
                return None
            return cleaned_label
        first = options.get("1")
        if first:
            cleaned_label = _clean_option_label(first)
            if _NON_EXECUTABLE_OPTION_RE.search(cleaned_label):
                return None
            return cleaned_label
        return None

    choice = _choice(user_text)
    if choice.isdigit():
        return None

    extraction = extract_slot_value(user_text, pending)
    if extraction.confidence in {"high", "medium"} and extraction.value:
        return extraction.value

    return None

def _last_assistant_options(context: ContextPackage) -> dict[str, str]:
    assistant_text = ""
    for turn in reversed(context.recent_history):
        if turn.role == "assistant" and turn.content:
            assistant_text = turn.content
            break

    options: dict[str, str] = {}
    for line in assistant_text.splitlines():
        match = re.match(r"^\s*(\d+)\.\s+(.+?)\s*$", line)
        if not match:
            continue
        number, label = match.groups()
        options[number] = label.strip()
    return options


def _selected_option_label(choice: str, options: dict[str, str]) -> str | None:
    if choice in options:
        return options[choice]
    return None


def _previous_user_intent(context: ContextPackage) -> str:
    for turn in reversed(context.recent_history):
        if turn.role == "user" and turn.content:
            return _normalized(turn.content)
    return ""


def _intent_wants_open(text: str) -> bool:
    return bool(re.search(r"\b(abre|abrir|open|navegador|pagina|página|sitio|web|ll[eé]vame|llevame|muestra|mu[eé]strame)\b", text, re.I))


def _intent_wants_search(text: str) -> bool:
    return bool(re.search(r"\b(busca|buscar|investiga|consulta|informaci[oó]n|documentaci[oó]n|docs?)\b", text, re.I))


def _clean_option_label(label: str) -> str:
    text = (label or "").strip().strip(" .,:;!?¿¡")
    text = re.sub(
        r"^(abrir|abre|buscar|busca|usar|usa|sí,\s*usar|si,\s*usar)\s+",
        "",
        text,
        flags=re.I,
    ).strip()
    return text.strip(" .,:;!?¿¡")


def _strip_action_prefix(text: str) -> str:
    return re.sub(
        r"^(abrir|abre|buscar|busca|usar|usa|sitio|p[aá]gina|url)\s+",
        "",
        text.strip(),
        flags=re.I,
    ).strip()


def _resolve_window_action(text: str, selected_label: str | None = None) -> str | None:
    value = _normalized(selected_label or text)
    value = _clean_option_label(value)
    value = _choice(value)

    if value == "1" or "izquierda" in value or value == "left":
        return "left"
    if value == "2" or "derecha" in value or value == "right":
        return "right"
    if value == "3" or "centro" in value or "centr" in value or value == "center":
        return "center"
    if value == "4":
        return None
    if "pantalla completa" in value or "maxim" in value or "llen" in value or value == "fill":
        return "fill"
    if "arriba" in value or value == "top":
        return "top"
    if "abajo" in value or value == "bottom":
        return "bottom"
    return None


def _choice(text: str) -> str:
    text = _normalized(text).strip(" .,:;!?¿¡")
    aliases = {
        "uno": "1",
        "opcion uno": "1",
        "opción uno": "1",
        "primero": "1",
        "primera": "1",
        "dos": "2",
        "opcion dos": "2",
        "opción dos": "2",
        "segundo": "2",
        "segunda": "2",
        "tres": "3",
        "opcion tres": "3",
        "opción tres": "3",
        "tercero": "3",
        "tercera": "3",
        "cuatro": "4",
        "opcion cuatro": "4",
        "opción cuatro": "4",
    }
    return aliases.get(text, text)


def _looks_like_url_or_domain(text: str) -> bool:
    compact = text.strip()
    return bool(
        _URL_RE.search(compact)
        or re.search(r"\b(?:[a-z0-9-]+\.)+(?:[a-z]{2,})(?:/[^\s)>,]*)?\b", compact, re.I)
    )


def _looks_like_new_request(text: str) -> bool:
    return bool(_OPERATIONAL_NEW_REQUEST_RE.search(text))


def _looks_like_app_name(text: str) -> bool:
    value = text.strip()
    if not _APPISH_RE.match(value):
        return False
    if len(value.split()) > 4:
        return False
    if _looks_like_new_request(value):
        return False
    return True


def _selected_tool_names(selected_tools: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for tool in selected_tools or []:
        if isinstance(tool, dict):
            name = tool.get("name")
        else:
            name = getattr(tool, "name", None)
        if isinstance(name, str) and name:
            names.add(name)
    return names


def _normalized(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _infer_pending_from_last_assistant(context: ContextPackage) -> str | None:
    for turn in reversed(context.recent_history):
        if turn.role != "assistant" or not turn.content:
            continue

        text = _normalized(turn.content)

        if "qué página" in text or "que pagina" in text or "sitio quieres abrir" in text or "url" in text:
            return "target_url"

        if "qué quieres que busque" in text or "que quieres que busque" in text or "tema exacto" in text:
            return "search_query"

        if "acción quieres hacer con la ventana" in text or "accion quieres hacer con la ventana" in text:
            return "window_action"

        if "qué app quieres abrir" in text or "que app quieres abrir" in text:
            return "target_app"

        if "qué quieres crear" in text or "que quieres crear" in text or "canva" in text or "diseño" in text:
            return "target_workflow_or_platform"

        break

    return None
