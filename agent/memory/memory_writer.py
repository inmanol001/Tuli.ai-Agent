from __future__ import annotations

from typing import Any

from agent.memory.learning_memory import record_learning_memory


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except Exception:
            return {}
    if hasattr(value, "__dict__"):
        try:
            return dict(value.__dict__)
        except Exception:
            return {}
    return {}


def _walk(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)


def _extract_tool_call(response: Any) -> dict[str, Any]:
    response_dict = _as_dict(response)

    tool_calls = response_dict.get("tool_calls")
    if isinstance(tool_calls, list) and tool_calls:
        first = _as_dict(tool_calls[0])
        if first.get("tool_name"):
            return first

    debug = response_dict.get("debug") or {}
    if not isinstance(debug, dict):
        debug = {}

    direct = _as_dict(debug.get("tool_call"))
    if direct.get("tool_name"):
        return direct

    fallback = _as_dict(debug.get("tool_planner_fallback_tool_call"))
    if fallback.get("tool_name"):
        return fallback

    action_run = _as_dict(debug.get("action_run"))
    action_tool_call = _as_dict(action_run.get("tool_call"))
    if action_tool_call.get("tool_name"):
        return action_tool_call

    for node in _walk(debug):
        if node.get("tool_name") and isinstance(node.get("arguments"), dict):
            return node

    return {}


def _extract_tool_result(response: Any) -> dict[str, Any]:
    response_dict = _as_dict(response)
    debug = response_dict.get("debug") or {}
    if not isinstance(debug, dict):
        debug = {}

    # Importante:
    # Solo aceptamos tool_result del turno actual.
    # NO caminar todo debug, porque context.session_state.conversation_state.last.tool_result
    # puede contener una herramienta vieja y contaminar learning_memory.
    direct = _as_dict(debug.get("tool_result"))
    if "success" in direct:
        return direct

    action_run = _as_dict(debug.get("action_run"))
    action_result = _as_dict(action_run.get("tool_result") or action_run.get("result"))
    if "success" in action_result:
        return action_result

    return {}


def _extract_intent(response: Any) -> str:
    response_dict = _as_dict(response)
    debug = response_dict.get("debug") or {}
    if not isinstance(debug, dict):
        return "action"

    context = debug.get("context") or {}
    if not isinstance(context, dict):
        return "action"

    router_decision = context.get("router_decision") or {}
    if not isinstance(router_decision, dict):
        return "action"

    intent = router_decision.get("intent")
    return str(intent or "action")


def _extract_skill(response: Any, tool_name: str | None = None) -> str | None:
    response_dict = _as_dict(response)
    debug = response_dict.get("debug") or {}
    if not isinstance(debug, dict):
        return tool_name

    context = debug.get("context") or {}
    if not isinstance(context, dict):
        return tool_name

    selected_skills = context.get("selected_skills") or []
    if isinstance(selected_skills, list) and selected_skills:
        first = selected_skills[0]
        if isinstance(first, dict) and first.get("name"):
            return str(first["name"])
        if isinstance(first, str):
            return first

    return tool_name


def record_learning_from_completed_turn(
    store: Any,
    *,
    user_message: str,
    response: Any,
) -> bool:
    """
    Guarda un aprendizaje estructurado solo si hubo ejecución real exitosa.

    V1 no decide rutas todavía.
    V1 solo escribe memoria auditable.
    """
    if store is None:
        return False

    user_phrase = (user_message or "").strip()
    if not user_phrase:
        return False

    tool_call = _extract_tool_call(response)
    tool_result = _extract_tool_result(response)

    tool_name = tool_call.get("tool_name") or tool_result.get("tool_name")
    if not tool_name:
        return False

    if tool_result.get("success") is not True:
        return False

    intent = _extract_intent(response)
    skill = _extract_skill(response, str(tool_name))

    evidence = {
        "tool_call": tool_call,
        "tool_result": tool_result,
        "source": "gateway_completed_turn",
    }

    record_learning_memory(
        store,
        user_phrase=user_phrase,
        correct_intent=intent,
        correct_tool=str(tool_name),
        correct_skill=skill,
        confidence=0.65,
        status="temporary",
        source="gateway",
        evidence=evidence,
        notes="auto-recorded from successful tool execution",
    )

    return True
