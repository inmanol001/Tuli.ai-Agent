from __future__ import annotations

from typing import Any

from agent.capabilities.tools.schemas import ToolCall


class PlayRandomYoutubeVideoActionMacro:
    """Recipe macro: open Chrome and search YouTube for a random video."""

    name = "play_random_youtube_video"

    def build_steps(self, inputs: dict[str, Any]) -> list[ToolCall]:
        query = (inputs.get("query") or "random video").strip() or "random video"
        return [
            ToolCall(tool_name="open_app", arguments={"app_name": "Google Chrome"}),
            ToolCall(
                tool_name="browser_search",
                arguments={"query": query, "target": "youtube"},
            ),
        ]
