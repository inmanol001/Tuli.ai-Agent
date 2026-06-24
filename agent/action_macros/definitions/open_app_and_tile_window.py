from __future__ import annotations

from agent.capabilities.tools.schemas import ToolCall


class OpenAppAndTileWindowActionMacro:
    name = "open_app_and_tile_window"

    def build_steps(self, inputs) -> list[ToolCall]:
        app_name = inputs.get("app_name", "")
        window_action = inputs.get("window_action", "")
        return [
            ToolCall(tool_name="open_app", arguments={"app_name": app_name}),
            ToolCall(tool_name="macos_observe_frontmost", arguments={}),
            ToolCall(
                tool_name="window_native_tiling",
                arguments={"action": window_action},
            ),
        ]
