from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from agent.gateway.message_types import AgentResponse


PREVIEW_LIMIT = 240


def preview(value: Any, limit: int = PREVIEW_LIMIT) -> str:
    text = str(value) if value is not None else ""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def build_dev_event(response: AgentResponse) -> dict[str, Any]:
    debug = response.debug or {}
    return {
        "ts": datetime.now(UTC).isoformat(),
        "session_id": response.session_id,
        "status": response.status,
        "route": response.route,
        "needs_user_input": response.needs_user_input,
        "router": summarize_router(debug),
        "session_state": summarize_session_state(debug),
        "capabilities": summarize_capabilities(debug),
        "tool_planner": summarize_tool_planner(debug),
        "rag": summarize_rag(debug),
        "tool_calls": summarize_tool_calls(response),
        "tool_result": summarize_tool_result(debug),
        "reflection": summarize_reflection(debug),
        "memory": summarize_memory(response, debug),
    }


def summarize_router(debug: dict[str, Any]) -> dict[str, Any]:
    router = debug.get("router") or {}
    decision = router.get("decision") or {}
    return {
        "intent": decision.get("intent"),
        "domain": decision.get("domain"),
        "action": decision.get("action"),
        "needs_tool": decision.get("needs_tool"),
        "needs_clarification": decision.get("needs_clarification"),
        "needs_memory": decision.get("needs_memory"),
        "needs_rag": decision.get("needs_rag"),
        "needs_vision": decision.get("needs_vision"),
        "risk_level": decision.get("risk_level"),
        "corrected": router.get("corrected"),
        "model_used": router.get("model_used"),
        "raw_preview": preview(router.get("raw")),
    }


def summarize_session_state(debug: dict[str, Any]) -> dict[str, Any]:
    context = debug.get("context") or {}
    state = context.get("session_state") or {}
    return {
        "pending_clarification": state.get("pending_clarification"),
        "pending_confirmation": state.get("pending_confirmation"),
        "previous_route": state.get("previous_route"),
        "current_route": state.get("current_route"),
    }


def summarize_capabilities(debug: dict[str, Any]) -> dict[str, Any]:
    context = debug.get("context") or {}
    tools = []
    for tool in context.get("selected_tools") or []:
        tools.append(
            {
                "name": tool.get("name"),
                "active": tool.get("active"),
                "declared": tool.get("declared"),
                "risk_level": tool.get("risk_level"),
            }
        )
    return {
        "plugins": [
            item.get("name") for item in context.get("selected_plugins") or []
        ],
        "skills": [item.get("name") for item in context.get("selected_skills") or []],
        "tools": tools,
    }


def summarize_tool_planner(debug: dict[str, Any]) -> dict[str, Any] | None:
    planner = debug.get("tool_planner")
    if not planner:
        return None
    return {
        "model": planner.get("model_used"),
        "content": preview(planner.get("content")),
        "tool_calls": planner.get("tool_calls") or [],
        "error": planner.get("error"),
        "no_tool_reason": planner.get("no_tool_reason"),
    }


def summarize_rag(debug: dict[str, Any]) -> dict[str, Any]:
    context = debug.get("context") or {}
    snippets = context.get("rag_snippets") or []
    return {
        "count": len(snippets),
        "sources": [snippet.get("source") for snippet in snippets if snippet.get("source")],
        "snippets": [
            {
                "source": snippet.get("source"),
                "score": snippet.get("score"),
                "preview": preview(snippet.get("text")),
            }
            for snippet in snippets[:3]
        ],
    }


def summarize_tool_calls(response: AgentResponse) -> list[dict[str, Any]]:
    calls = []
    for call in response.tool_calls:
        calls.append(
            {
                "tool_name": call.get("tool_name"),
                "arguments": call.get("arguments"),
                "risk_level": call.get("risk_level"),
                "requires_confirmation": call.get("requires_confirmation"),
            }
        )
    return calls


def summarize_tool_result(debug: dict[str, Any]) -> dict[str, Any] | None:
    result = debug.get("tool_result")
    if not result:
        return None
    data = result.get("data") or {}
    return {
        "tool_name": result.get("tool_name"),
        "success": result.get("success"),
        "error": result.get("error"),
        "metadata": result.get("metadata"),
        "data_preview": preview(data),
    }


def summarize_reflection(debug: dict[str, Any]) -> dict[str, Any] | None:
    trace = debug.get("reflection")
    if not trace:
        return None
    attempts = []
    for item in trace:
        tool_result = item.get("tool_result") or {}
        decision = item.get("decision") or {}
        attempts.append(
            {
                "attempt_number": item.get("attempt_number"),
                "execution_number": item.get("execution_number"),
                "success": tool_result.get("success"),
                "decision_reason": decision.get("reason"),
                "should_retry": decision.get("should_retry"),
                "should_stop": decision.get("should_stop"),
            }
        )
    return {
        "retry_count": debug.get("retry_count", 0),
        "retry_reason": debug.get("retry_reason"),
        "final_stop_reason": debug.get("final_stop_reason"),
        "attempts": attempts,
    }


def summarize_memory(response: AgentResponse, debug: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": response.session_id,
        "session_persisted": True,
        "turns_count": "not_available",
        "pending_state": summarize_session_state(debug),
    }
