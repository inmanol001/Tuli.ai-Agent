import subprocess

import pytest

from agent.gateway.gateway import Gateway
from agent.gateway.gateway_logger import GatewayLogger
from agent.gateway.session_manager import SessionManager
from agent.gateway.tool_fallbacks import fallback_browser_search_call
from agent.models.main_model import MainModel
from agent.models.tool_finalizer import ToolFinalizerResult
from agent.models.tool_planner import ToolPlannerResult
from agent.response_action.controller import ResponseController
from agent.router.router_schema import RouterDecision, RouterResult
from agent.memory.sqlite_store import SQLiteStore
from agent.action_macros.schemas import ActionMacroPlan


class FakeActionReadyRouter:
    def route(self, user_text: str) -> RouterResult:
        return RouterResult(
            decision=RouterDecision(
                intent="action",
                domain="browser",
                action="open",
                route="action_ready",
                needs_tool=True,
                suggested_plugins=["browser"],
                suggested_skills=["browser_search"],
                suggested_tools=["browser_search"],
            ),
            model_used="fake",
            raw="{}",
            corrected=True,
        )


class NoToolPlanner:
    def __init__(self, content: str = "I can help with that.") -> None:
        self.content = content
        self.calls = []

    def plan(self, context):
        self.calls.append(context)
        return ToolPlannerResult(
            model_used="fake-tool-planner",
            content=self.content,
            tool_calls=[],
            no_tool_reason="no_native_tool_call",
        )


class NoSelector:
    def select(self, context):
        return ActionMacroPlan(selected=False)


class FakeMainModel(MainModel):
    def respond(self, context):
        return "respuesta"


class FakeToolFinalizer:
    def __init__(self) -> None:
        self.calls = []

    def finalize(self, *, user_message, tool_call, tool_result):
        self.calls.append(
            {
                "user_message": user_message,
                "tool_call": tool_call,
                "tool_result": tool_result,
            }
        )
        text = f"Abrí {tool_result.data.get('url', '')}"
        return ToolFinalizerResult(model_used="fake", text=text, fallback=True)


class RunRecorder:
    def __init__(self) -> None:
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")


@pytest.mark.parametrize(
    "user_text, expected_query, expected_target, expected_kind",
    [
        ("abre canva", "canva", "auto", "browser_search_known_destination"),
        (
            "quiero ver el sitio de Ollama abierto",
            "ollama",
            "auto",
            "browser_search_known_destination",
        ),
        ("abre github", "github", "auto", "browser_search_known_destination"),
        (
            "abre docs.ollama.com",
            "docs.ollama.com",
            "auto",
            "browser_search_domain",
        ),
        (
            "abre https://docs.ollama.com",
            "https://docs.ollama.com",
            "url",
            "browser_search_direct_url",
        ),
    ],
)
def test_fallback_browser_search_call_resolves_direct_open_intents(
    user_text, expected_query, expected_target, expected_kind
):
    result = fallback_browser_search_call(
        user_text,
        selected_tools=[{"name": "browser_search", "active": True, "declared": True}],
    )

    assert result is not None
    tool_call, kind = result
    assert tool_call.tool_name == "browser_search"
    assert tool_call.arguments == {"query": expected_query, "target": expected_target}
    assert kind == expected_kind


@pytest.mark.parametrize(
    "user_text",
    [
        "investiga ollama tool calling",
        "compara qwen3 y llama3",
        "busca en internet noticias de inteligencia artificial",
    ],
)
def test_fallback_browser_search_call_does_not_trigger_for_non_open_intents(user_text):
    result = fallback_browser_search_call(
        user_text,
        selected_tools=[{"name": "browser_search", "active": True, "declared": True}],
    )

    assert result is None


def test_gateway_uses_browser_search_fallback_when_planner_returns_no_tool_call(tmp_path, monkeypatch):
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    gateway = Gateway(
        session_manager=SessionManager(store=SQLiteStore(tmp_path / "memory.db")),
        router=FakeActionReadyRouter(),
        response_controller=ResponseController(
            main_model=FakeMainModel(),
            tool_planner=NoToolPlanner(),
            tool_finalizer=FakeToolFinalizer(),
            full_workflow_selector=NoSelector(),
            action_macro_selector=NoSelector(),
        ),
        logger=GatewayLogger(tmp_path / "logs"),
    )

    response = gateway.handle_message("abre canva", debug=True)

    assert response.status == "ok"
    assert response.route == "action_ready"
    assert response.tool_calls[0]["tool_name"] == "browser_search"
    assert response.tool_calls[0]["arguments"] == {"query": "canva", "target": "auto"}
    assert response.debug["tool_planner_fallback"] == "browser_search_known_destination"
    assert response.debug["model_action"]["tool_call"]["arguments"] == {
        "query": "canva",
        "target": "auto",
    }
    assert recorder.calls[0][0] == ["/usr/bin/open", "https://www.canva.com"]
