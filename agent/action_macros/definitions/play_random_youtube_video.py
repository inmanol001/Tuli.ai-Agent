from __future__ import annotations

from typing import Any

from agent.capabilities.tools.schemas import ToolCall
from agent.action_macros.open_ended_search_resolver import resolve_open_ended_search_query


class PlayRandomYoutubeVideoActionMacro:
    """Recipe macro: search YouTube for a random/open-ended video request."""

    name = "play_random_youtube_video"

    def build_steps(self, inputs: dict[str, Any]) -> list[ToolCall]:
        open_ended = bool(inputs.get("open_ended"))
        topic_hint = (inputs.get("topic_hint") or "").strip()
        raw_query = (inputs.get("query") or "").strip()
        user_context = (inputs.get("user_context") or "").strip()

        if open_ended:
            query = resolve_open_ended_search_query(
                target="youtube",
                query=raw_query,
                topic_hint=topic_hint,
                user_context=user_context,
                fallback="documental corto interesante",
            )
        else:
            query = raw_query or "documental corto interesante"

        return [
            ToolCall(
                tool_name="browser_search",
                arguments={"query": query, "target": "youtube"},
            ),
        ]
