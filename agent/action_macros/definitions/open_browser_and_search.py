from __future__ import annotations

from agent.capabilities.tools.schemas import ToolCall
from agent.action_macros.open_ended_search_resolver import resolve_open_ended_search_query


class OpenBrowserAndSearchActionMacro:
    """Recipe macro: open a browser and perform a web search."""

    name = "open_browser_and_search"

    def build_steps(self, inputs) -> list[ToolCall]:
        query = (inputs.get("query") or "").strip()
        target = (inputs.get("target") or "web").strip()
        open_ended = bool(inputs.get("open_ended"))
        topic_hint = (inputs.get("topic_hint") or "").strip()
        user_context = (inputs.get("user_context") or "").strip()

        if open_ended:
            query = resolve_open_ended_search_query(
                target=target,
                query=query,
                topic_hint=topic_hint,
                user_context=user_context,
                fallback="temas interesantes de tecnología y ciencia",
            )

        return [
            ToolCall(
                tool_name="browser_search",
                arguments={"query": query, "target": target},
            ),
        ]
