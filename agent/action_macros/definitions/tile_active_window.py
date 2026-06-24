from __future__ import annotations

from agent.capabilities.tools.schemas import ToolCall


class TileActiveWindowActionMacro:
    name = "tile_active_window"

    def build_steps(self, inputs) -> list[ToolCall]:
        window_action = inputs.get("window_action", "")
        return [
            ToolCall(tool_name="macos_observe_frontmost", arguments={}),
            ToolCall(
                tool_name="window_native_tiling",
                arguments={"action": window_action},
            ),
        ]
