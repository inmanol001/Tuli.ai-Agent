from agent.capabilities.tools.schemas import ToolCall
from agent.gateway.tool_fallbacks import fallback_action_guard_call
from agent.gateway.gateway import Gateway
from agent.models.main_model import MainModel
from agent.models.tool_planner import ToolPlannerResult
from agent.response_action.controller import ResponseController


def debug_for(action_type: str, target: str) -> dict:
    return {
        "action_guard_recovered": True,
        "action_intent_guard": {
            "action_required": True,
            "reason": "verb_plus_target",
            "action_type": action_type,
            "target": target,
            "confidence": "high",
            "missing_info": [],
            "suggested_route": "action_ready",
            "suggested_tools": [],
        },
    }


def test_fallback_action_guard_open_app():
    result = fallback_action_guard_call(debug_for("open", "Figma"))

    assert result is not None
    tool_call, reason = result
    assert reason == "action_guard_open_app"
    assert tool_call.tool_name == "open_app"
    assert tool_call.arguments == {"app_name": "Figma"}


def test_fallback_action_guard_show_browser_search():
    result = fallback_action_guard_call(debug_for("show", "Google"))

    assert result is not None
    tool_call, reason = result
    assert reason == "action_guard_browser_search"
    assert tool_call.tool_name == "browser_search"
    assert tool_call.arguments == {"query": "Google", "target": "auto"}


def test_fallback_action_guard_search_web_search():
    result = fallback_action_guard_call(debug_for("search", "documentación de Ollama"))

    assert result is not None
    tool_call, reason = result
    assert reason == "action_guard_web_search"
    assert tool_call.tool_name == "web_search"
    assert tool_call.arguments == {"query": "documentación de Ollama", "max_results": 5}


def test_fallback_action_guard_mission_control():
    result = fallback_action_guard_call(debug_for("activate", "Mission Control"))

    assert result is not None
    tool_call, reason = result
    assert reason == "action_guard_mission_control"
    assert tool_call.tool_name == "macos_space_mission_control"
    assert tool_call.arguments == {}


def test_fallback_action_guard_window_left():
    result = fallback_action_guard_call(debug_for("window_move", "la ventana a la izquierda"))

    assert result is not None
    tool_call, reason = result
    assert reason == "action_guard_window_left"
    assert tool_call.tool_name == "window_native_tiling"
    assert tool_call.arguments == {"action": "left"}


class ExplodingMainModel(MainModel):
    def respond(self, context):
        raise AssertionError("MainModel no debe responder acciones recuperadas")


class NoToolPlanner:
    def plan(self, context):
        return ToolPlannerResult(
            model_used="fake-no-tool",
            content="I cannot call tools.",
            tool_calls=[],
            raw={"fake": True},
            error=None,
            no_tool_reason="no_native_tool_call",
        )


class CapturingExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, call: ToolCall):
        self.calls.append(call)
        from agent.executor.results import ToolResult
        return ToolResult(
            tool_name=call.tool_name,
            success=True,
            data=dict(call.arguments),
            metadata={"test": True},
        )


def test_gateway_uses_action_guard_fallback_when_toolplanner_returns_no_call():
    executor = CapturingExecutor()
    gateway = Gateway(
        response_controller=ResponseController(
            main_model=ExplodingMainModel(),
            tool_planner=NoToolPlanner(),
            executor=executor,
        ),
    )

    response = gateway.handle_message("abre Figma", debug=True)

    assert executor.calls
    assert executor.calls[0].tool_name == "open_app"
    assert executor.calls[0].arguments == {"app_name": "Figma"}
    assert response.debug["tool_planner_fallback"] == "action_guard_open_app"
    assert response.debug["tool_planner_fallback_tool_call"]["tool_name"] == "open_app"
