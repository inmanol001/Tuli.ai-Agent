from agent.conversation_state.state import (
    default_conversation_state,
    extract_web_results,
    update_conversation_state_from_response,
)
from agent.executor.results import ToolResult
from agent.gateway.gateway import Gateway
from agent.models.main_model import MainModel
from agent.models.tool_planner import ToolPlannerResult
from agent.capabilities.tools.schemas import ToolCall
from agent.response_action.controller import ResponseController


class FakeResponse:
    def __init__(self, *, status="ok", route="action_ready", text="ok", tool_calls=None, debug=None):
        self.status = status
        self.route = route
        self.text = text
        self.tool_calls = tool_calls or []
        self.debug = debug or {}


def test_extract_web_results_normalizes_results():
    tool_result = {
        "tool_name": "web_search",
        "success": True,
        "data": {
            "results": [
                {
                    "title": "Ollama Tool Calling",
                    "url": "https://docs.ollama.com/capabilities/tool-calling",
                    "snippet": "Tools docs",
                }
            ]
        },
        "metadata": {},
    }

    results = extract_web_results(tool_result)

    assert results == [
        {
            "index": 1,
            "title": "Ollama Tool Calling",
            "url": "https://docs.ollama.com/capabilities/tool-calling",
            "snippet": "Tools docs",
        }
    ]


def test_conversation_state_updates_web_results_and_expected_next_step():
    state = default_conversation_state()
    response = FakeResponse(
        status="ok",
        route="action_ready",
        tool_calls=[
            {
                "tool_name": "web_search",
                "arguments": {"query": "Ollama tool calling"},
                "risk_level": "low",
                "requires_confirmation": False,
            }
        ],
        debug={
            "tool_result": {
                "tool_name": "web_search",
                "success": True,
                "data": {
                    "query": "Ollama tool calling",
                    "results": [
                        {
                            "title": "Ollama Tool Calling",
                            "url": "https://docs.ollama.com/capabilities/tool-calling",
                            "snippet": "Tools docs",
                        }
                    ],
                },
                "error": None,
                "metadata": {"test": True},
            }
        },
    )

    updated = update_conversation_state_from_response(
        state,
        user_text="búscame documentación de Ollama tool calling",
        response=response,
    )

    assert updated["conversation"]["active_mode"] == "research"
    assert updated["conversation"]["expected_next_step"] == "user_may_open_or_refine_web_result"
    assert updated["last"]["tool"] == "web_search"
    assert updated["last"]["error"] is None
    assert updated["last"]["web_results"][0]["url"] == "https://docs.ollama.com/capabilities/tool-calling"
    assert updated["events"][-1]["type"] == "web_results_updated"


def test_conversation_state_updates_last_error_on_tool_failure():
    state = default_conversation_state()
    response = FakeResponse(
        status="error",
        route="action_ready",
        tool_calls=[
            {
                "tool_name": "open_app",
                "arguments": {"app_name": "Figma"},
                "risk_level": "low",
                "requires_confirmation": False,
            }
        ],
        debug={
            "tool_result": {
                "tool_name": "open_app",
                "success": False,
                "data": {},
                "error": "Figma not found",
                "metadata": {"test": True},
            }
        },
    )

    updated = update_conversation_state_from_response(
        state,
        user_text="abre Figma",
        response=response,
    )

    assert updated["conversation"]["active_mode"] == "action"
    assert updated["conversation"]["expected_next_step"] == "user_may_retry_or_change_request"
    assert updated["last"]["tool"] == "open_app"
    assert updated["last"]["error"] == "Figma not found"
    assert updated["last"]["action"]["tool_name"] == "open_app"
    assert updated["events"][-1]["type"] == "tool_error"


class ExplodingMainModel(MainModel):
    def respond(self, context):
        raise AssertionError("No debe responder chat en esta prueba")


class FakePlanner:
    def plan(self, context):
        return ToolPlannerResult(
            model_used="fake",
            tool_calls=[
                ToolCall(
                    tool_name="web_search",
                    arguments={"query": "Ollama tool calling", "max_results": 3},
                    risk_level="low",
                    requires_confirmation=False,
                )
            ],
            raw={"fake": True},
        )


class FakeExecutor:
    def execute(self, call):
        return ToolResult(
            tool_name=call.tool_name,
            success=True,
            data={
                "query": call.arguments.get("query"),
                "results": [
                    {
                        "title": "Ollama Tool Calling",
                        "url": "https://docs.ollama.com/capabilities/tool-calling",
                        "snippet": "Tools docs",
                    }
                ],
            },
            metadata={"test": True},
        )


class FakeFinalizer:
    def finalize(self, *, user_message, tool_call, tool_result):
        from agent.models.tool_finalizer import ToolFinalizerResult

        return ToolFinalizerResult(
            model_used="fake",
            text="Encontré resultados de búsqueda.",
        )


def test_gateway_persists_and_exposes_conversation_state(tmp_path):
    from agent.gateway.session_manager import SessionManager
    from agent.memory.sqlite_store import SQLiteStore

    store = SQLiteStore(str(tmp_path / "memory.sqlite3"))
    gateway = Gateway(
        session_manager=SessionManager(store=store),
        response_controller=ResponseController(
            main_model=ExplodingMainModel(),
            tool_planner=FakePlanner(),
            executor=FakeExecutor(),
            tool_finalizer=FakeFinalizer(),
        ),
    )

    response = gateway.handle_message("búscame documentación de Ollama tool calling", debug=True)
    session = gateway.sessions.get_or_create(response.session_id)

    assert session.conversation_state["last"]["tool"] == "web_search"
    assert session.conversation_state["last"]["web_results"][0]["url"] == "https://docs.ollama.com/capabilities/tool-calling"

    hydrated = gateway.sessions.hydrate_session(response.session_id)
    assert hydrated is not None
    assert hydrated.conversation_state["last"]["tool"] == "web_search"

    second_response = gateway.handle_message("búscame documentación de Ollama tool calling", session_id=response.session_id, debug=True)
    state_in_context = second_response.debug["context"]["session_state"]["conversation_state"]

    assert state_in_context["last"]["tool"] == "web_search"
    assert state_in_context["last"]["web_results"][0]["title"] == "Ollama Tool Calling"
