from agent.capabilities.tools.registry import ToolRegistry
from agent.capabilities.tools.schemas import ToolCall
from agent.capabilities.tools.macos_window_tools import NATIVE_TILING_ACTIONS
from agent.gateway.errors import ToolBlockedError


class ToolValidator:
    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or ToolRegistry()

    def validate(self, call: ToolCall) -> None:
        tool = self.registry.get(call.tool_name)
        if tool is None:
            raise ToolBlockedError(f"Tool not registered: {call.tool_name}")
        if not tool.declared:
            raise ToolBlockedError(f"Tool not declared for current phase: {call.tool_name}")
        if not isinstance(tool.parameters, dict):
            raise ToolBlockedError(f"Tool missing valid parameter schema: {call.tool_name}")
        if call.tool_name == "browser_search":
            target = (call.arguments.get("target") or "auto").strip().lower()
            query = (call.arguments.get("query") or "").strip()
            if not query and target not in {"google_home", "youtube_home"}:
                raise ToolBlockedError("browser_search requires a query argument")
        if call.tool_name == "open_app" and not call.arguments.get("app_name"):
            raise ToolBlockedError("open_app requires an app_name argument")
        if call.tool_name == "window_native_tiling":
            action = call.arguments.get("action")
            if not isinstance(action, str) or isinstance(action, bool):
                raise ToolBlockedError("window_native_tiling requires a string action argument")
            if action.strip().lower() not in NATIVE_TILING_ACTIONS:
                raise ToolBlockedError(
                    "window_native_tiling supports a fixed allowlist of native window actions"
                )
        if call.tool_name == "macos_space_switch_desktop_number":
            number = call.arguments.get("number")
            if not isinstance(number, int) or isinstance(number, bool):
                raise ToolBlockedError("macos_space_switch_desktop_number requires an integer number argument")
            if number < 1 or number > 9:
                raise ToolBlockedError("macos_space_switch_desktop_number supports desktop numbers 1 through 9")
        if tool.risk_level not in {"low", "medium", "high"}:
            raise ToolBlockedError(f"Tool missing valid risk level: {call.tool_name}")
        if not tool.active:
            raise ToolBlockedError(f"Tool inactive in current phase: {call.tool_name}")
