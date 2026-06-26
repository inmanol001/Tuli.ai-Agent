from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any


MAX_EVENTS = 50
MAX_WEB_RESULTS = 10
MAX_TEXT = 5000


def now_machine_snapshot() -> dict[str, Any]:
    now = datetime.now().astimezone()
    return {
        "timestamp": now.isoformat(),
        "timezone": str(now.tzinfo),
    }


def default_conversation_state() -> dict[str, Any]:
    machine = now_machine_snapshot()
    return {
        "conversation": {
            "active_mode": None,
            "active_topic": None,
            "expected_next_step": None,
        },
        "last": {
            "tool": None,
            "tool_result": None,
            "error": None,
            "action": None,
            "web_results": [],
        },
        "machine": {
            "timestamp": machine["timestamp"],
            "timezone": machine["timezone"],
        },
        "events": [],
    }


def normalize_conversation_state(value: Any) -> dict[str, Any]:
    state = default_conversation_state()
    if not isinstance(value, dict):
        return state

    conversation = value.get("conversation")
    if isinstance(conversation, dict):
        state["conversation"].update(conversation)

    last = value.get("last")
    if isinstance(last, dict):
        state["last"].update(last)
        if not isinstance(state["last"].get("web_results"), list):
            state["last"]["web_results"] = []

    machine = value.get("machine")
    if isinstance(machine, dict):
        state["machine"].update(machine)

    events = value.get("events")
    if isinstance(events, list):
        state["events"] = events[-MAX_EVENTS:]

    return state


def update_conversation_state_from_response(
    state: dict[str, Any] | None,
    *,
    user_text: str,
    response: Any,
) -> dict[str, Any]:
    next_state = normalize_conversation_state(deepcopy(state) if state else None)
    machine = now_machine_snapshot()
    next_state["machine"].update(machine)

    debug = getattr(response, "debug", None) or {}
    route = getattr(response, "route", None)
    status = getattr(response, "status", None)
    text = getattr(response, "text", "") or ""
    tool_calls = getattr(response, "tool_calls", None) or []
    tool_result = debug.get("tool_result")

    _update_conversation_block(
        next_state,
        user_text=user_text,
        route=route,
        status=status,
        tool_result=tool_result,
    )

    if tool_calls:
        first_call = tool_calls[0]
        next_state["last"]["action"] = {
            "tool_name": first_call.get("tool_name"),
            "arguments": first_call.get("arguments", {}),
            "route": route,
            "status": status,
            "timestamp": machine["timestamp"],
        }

    if tool_result:
        _update_tool_state(next_state, tool_result, machine["timestamp"])

    if status == "error" and not tool_result:
        next_state["last"]["error"] = _clip_text(text)
        _append_event(
            next_state,
            {
                "type": "response_error",
                "timestamp": machine["timestamp"],
                "route": route,
                "error": _clip_text(text),
            },
        )

    return normalize_conversation_state(next_state)


def _update_conversation_block(
    state: dict[str, Any],
    *,
    user_text: str,
    route: str | None,
    status: str | None,
    tool_result: dict[str, Any] | None,
) -> None:
    conversation = state["conversation"]
    tool_name = tool_result.get("tool_name") if isinstance(tool_result, dict) else None

    if tool_name == "web_search":
        conversation["active_mode"] = "research"
    elif route == "action_ready":
        conversation["active_mode"] = "action"
    elif route == "chat":
        conversation["active_mode"] = "chat"
    elif route:
        conversation["active_mode"] = route

    topic = _infer_topic(user_text)
    if topic:
        conversation["active_topic"] = topic

    if status == "needs_clarification":
        conversation["expected_next_step"] = "waiting_for_user_clarification"
    elif isinstance(tool_result, dict) and tool_result.get("tool_name") == "web_search" and tool_result.get("success") is True:
        conversation["expected_next_step"] = "user_may_open_or_refine_web_result"
    elif isinstance(tool_result, dict) and tool_result.get("success") is False:
        conversation["expected_next_step"] = "user_may_retry_or_change_request"
    elif status == "error":
        conversation["expected_next_step"] = "user_may_retry_or_change_request"
    elif route == "action_ready":
        conversation["expected_next_step"] = None


def _update_tool_state(
    state: dict[str, Any],
    tool_result: dict[str, Any],
    timestamp: str,
) -> None:
    last = state["last"]
    tool_name = tool_result.get("tool_name")
    success = tool_result.get("success")

    last["tool"] = tool_name
    last["tool_result"] = _safe_tool_result(tool_result)

    if success is False:
        last["error"] = _clip_text(tool_result.get("error") or "Tool failed.")
        _append_event(
            state,
            {
                "type": "tool_error",
                "timestamp": timestamp,
                "tool": tool_name,
                "error": last["error"],
            },
        )
        return

    last["error"] = None
    _append_event(
        state,
        {
            "type": "tool_success",
            "timestamp": timestamp,
            "tool": tool_name,
        },
    )

    if tool_name == "web_search":
        results = extract_web_results(tool_result)
        last["web_results"] = results
        _append_event(
            state,
            {
                "type": "web_results_updated",
                "timestamp": timestamp,
                "tool": tool_name,
                "count": len(results),
            },
        )


def extract_web_results(tool_result: dict[str, Any]) -> list[dict[str, Any]]:
    data = tool_result.get("data") or {}
    if not isinstance(data, dict):
        return []

    raw_results = (
        data.get("results")
        or data.get("items")
        or data.get("organic_results")
        or data.get("web_results")
        or []
    )

    if not isinstance(raw_results, list):
        return []

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_results[:MAX_WEB_RESULTS], start=1):
        if not isinstance(item, dict):
            continue

        url = (
            item.get("url")
            or item.get("link")
            or item.get("href")
            or item.get("source_url")
            or ""
        )
        title = item.get("title") or item.get("name") or url or f"Resultado {index}"
        snippet = item.get("snippet") or item.get("description") or item.get("content") or ""

        if not url:
            continue

        normalized.append(
            {
                "index": index,
                "title": _clip_text(str(title), 300),
                "url": str(url),
                "snippet": _clip_text(str(snippet), 700),
            }
        )

    return normalized


def _append_event(state: dict[str, Any], event: dict[str, Any]) -> None:
    events = state.setdefault("events", [])
    if not isinstance(events, list):
        events = []
        state["events"] = events
    events.append(event)
    state["events"] = events[-MAX_EVENTS:]


def _safe_tool_result(tool_result: dict[str, Any]) -> dict[str, Any]:
    # Guardamos el tool_result completo, pero limitamos strings gigantes.
    return _clip_nested(tool_result)


def _clip_nested(value: Any) -> Any:
    if isinstance(value, str):
        return _clip_text(value)
    if isinstance(value, list):
        return [_clip_nested(item) for item in value[:MAX_WEB_RESULTS]]
    if isinstance(value, dict):
        return {str(k): _clip_nested(v) for k, v in value.items()}
    return value


def _clip_text(value: Any, limit: int = MAX_TEXT) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


def _infer_topic(user_text: str) -> str | None:
    text = " ".join((user_text or "").strip().split())
    if not text:
        return None

    lowered = text.lower()
    prefixes = [
        "búscame",
        "buscame",
        "busca",
        "investiga",
        "consulta",
        "abre",
        "abrir",
        "muéstrame",
        "muestrame",
        "muestra",
        "explícame",
        "explicame",
        "qué es",
        "que es",
    ]

    for prefix in prefixes:
        if lowered.startswith(prefix + " "):
            return text[len(prefix):].strip(" :,-")[:200] or text[:200]

    return text[:200]
