from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from agent.clarification.pending_actions import pending_clarification_tool_call
from agent.capabilities.tools.schemas import ToolCall
from agent.gateway.direct_actions import direct_browser_search_call
from agent.gateway.message_types import ContextPackage
from agent.gateway.tool_fallbacks import fallback_web_result_reference_call
from agent.models.ollama_client import OllamaClient


TOOL_PLANNER_SYSTEM_PROMPT = """You are a macOS tool-calling agent.
You have tools for web search results, browser navigation/search, macOS apps, macOS observation, fixed macOS window actions, and fixed macOS Spaces actions.
When the user asks for an action or asks to observe current app/window state, call the matching tool.
Never say you cannot do something when a matching tool is available.
Do not pretend you executed an action.
Do not write JSON manually in content.
For normal conversation only, answer normally without tools.
"""


class ToolPlannerResult(BaseModel):
    model_used: str
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    no_tool_reason: str | None = None


class ToolPlanner:
    def __init__(
        self,
        client: OllamaClient | None = None,
        model: str = "llama3-groq-tool-use:8b",
    ) -> None:
        self.client = client or OllamaClient()
        self.model = model

    def plan(self, context: ContextPackage) -> ToolPlannerResult:
        pending_call = pending_clarification_tool_call(context)
        if pending_call is not None:
            tool_call, reason = pending_call
            return ToolPlannerResult(
                model_used="deterministic_pending_clarification",
                tool_calls=[tool_call],
                raw={"source": reason},
                no_tool_reason=None,
            )

        direct_call = fallback_web_result_reference_call(context)
        if direct_call is None:
            direct_call = direct_browser_search_call(
                context.user_message,
                context.selected_tools,
            )

        if direct_call is not None:
            tool_call, reason = direct_call
            return ToolPlannerResult(
                model_used="deterministic_direct_action",
                tool_calls=[tool_call],
                raw={"source": reason},
                no_tool_reason=None,
            )

        tools = self._ollama_tools(context.selected_tools)
        messages = self._messages(context)
        try:
            response = self.client.chat_with_tools(
                self.model,
                messages,
                tools,
                options={"temperature": 0},
            )
            content = self._content(response)
            tool_calls = self._tool_calls(response, context.selected_tools)
            return ToolPlannerResult(
                model_used=self.model,
                content=content,
                tool_calls=tool_calls,
                raw=self._raw_response(response),
                no_tool_reason=None if tool_calls else "no_native_tool_call",
            )
        except Exception as exc:
            return ToolPlannerResult(
                model_used=self.model,
                error=str(exc),
                no_tool_reason="tool_planner_error",
            )

    def _messages(self, context: ContextPackage) -> list[dict[str, str]]:
        session_lines = [
            f"pending_clarification={context.session_state.get('pending_clarification')}",
            f"pending_confirmation={context.session_state.get('pending_confirmation')}",
            f"previous_route={context.session_state.get('previous_route')}",
            f"current_route={context.session_state.get('current_route')}",
        ]
        tool_names = ", ".join(tool.get("name", "") for tool in context.selected_tools)

        skill_sections = []
        for skill in context.selected_skills:
            name = skill.get("name", "unknown_skill")
            description = skill.get("description", "")
            content = skill.get("content", "") or ""
            if content:
                skill_sections.append(
                    f"## Skill: {name}\n"
                    f"Description: {description}\n\n"
                    f"{content}"
                )

        selected_skill_content = "\n\n".join(skill_sections) or "(none)"

        return [
            {"role": "system", "content": TOOL_PLANNER_SYSTEM_PROMPT},
            {
                "role": "system",
                "content": (
                    "Available tools: "
                    f"{tool_names or '(none)'}\n"
                    "Selected plugins: "
                    f"{[plugin.get('name') for plugin in context.selected_plugins]}\n"
                    "Selected skills: "
                    f"{[skill.get('name') for skill in context.selected_skills]}\n\n"
                    "Selected skill instructions:\n"
                    f"{selected_skill_content}\n\n"
                    "Safety rules:\n- "
                    + "\n- ".join(context.safety_rules)
                    + "\nSession state:\n- "
                    + "\n- ".join(session_lines)
                ),
            },
            {"role": "user", "content": context.user_message},
        ]

    def _ollama_tools(self, selected_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tools = []
        for tool in selected_tools:
            if not tool.get("active") or not tool.get("declared"):
                continue
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters") or {
                            "type": "object",
                            "properties": {},
                        },
                    },
                }
            )
        return tools

    def _tool_calls(
        self, response: Any, selected_tools: list[dict[str, Any]]
    ) -> list[ToolCall]:
        selected_by_name = {tool.get("name"): tool for tool in selected_tools}
        message = self._get(response, "message", {})
        raw_calls = self._get(message, "tool_calls", []) or []
        normalized = []
        for raw_call in raw_calls:
            function = self._get(raw_call, "function", {})
            name = self._get(function, "name", None)
            if not name or name not in selected_by_name:
                continue
            arguments = self._get(function, "arguments", {}) or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            tool = selected_by_name[name]
            normalized.append(
                ToolCall(
                    tool_name=name,
                    arguments=arguments,
                    risk_level=tool.get("risk_level", "low"),
                    requires_confirmation=False,
                )
            )
        return normalized

    def _content(self, response: Any) -> str:
        message = self._get(response, "message", {})
        return self._get(message, "content", "") or ""

    def _raw_response(self, response: Any) -> dict[str, Any]:
        if hasattr(response, "model_dump"):
            return response.model_dump(mode="json")
        if isinstance(response, dict):
            return response
        return {"repr": repr(response)}

    def _get(self, value: Any, key: str, default: Any = None) -> Any:
        if isinstance(value, dict):
            return value.get(key, default)
        return getattr(value, key, default)
