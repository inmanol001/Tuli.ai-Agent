from __future__ import annotations

from agent.capabilities.tools.schemas import ToolCall


class OpenWorkSetupActionMacro:
    """Recipe macro: open the user's common work apps as a fixed sequence."""

    name = "open_work_setup"

    def build_steps(self, inputs) -> list[ToolCall]:
        steps = [
            ToolCall(tool_name="open_app", arguments={"app_name": "Google Chrome"}),
            ToolCall(tool_name="open_app", arguments={"app_name": "Visual Studio Code"}),
            ToolCall(tool_name="open_app", arguments={"app_name": "Terminal"}),
        ]
        if inputs.get("open_chatgpt", True):
            steps.append(
                ToolCall(
                    tool_name="open_url",
                    arguments={"url": "https://chatgpt.com"},
                )
            )
        return steps
