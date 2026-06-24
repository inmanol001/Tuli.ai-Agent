import json
import subprocess
from pathlib import Path

from agent.capabilities.tools.schemas import ToolCall
from agent.context_builder.builder import ContextBuilder
from agent.executor.results import ToolResult
from agent.gateway.gateway import Gateway
from agent.gateway.gateway_logger import GatewayLogger
from agent.gateway.message_types import AgentResponse
from agent.gateway.pipeline import Pipeline
from agent.gateway.session_manager import SessionManager
from agent.logging.dev_event_builder import build_dev_event
from agent.memory.sqlite_store import SQLiteStore
from agent.models.action_models import ModelAction
from agent.models.main_model import MainModel
from agent.models.tool_planner import ToolPlannerResult
from agent.response_action.controller import ResponseController
from agent.router.router_schema import RouterDecision, RouterResult
from agent.ui.cli import run_dev_console, run_repl
from agent.ui.dev_console import read_dev_events, render_dev_event


class ChatRouter:
    def route(self, user_text: str) -> RouterResult:
        return RouterResult(
            decision=RouterDecision(route="chat"),
            model_used="fake",
            raw="{}",
            corrected=True,
        )


class ActionRouter:
    def route(self, user_text: str) -> RouterResult:
        return RouterResult(
            decision=RouterDecision(
                intent="action",
                domain="browser",
                action="search",
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


class RagRouter:
    def route(self, user_text: str) -> RouterResult:
        return RouterResult(
            decision=RouterDecision(
                intent="rag",
                domain="knowledge_base",
                action="lookup",
                route="rag_lookup",
                needs_rag=True,
            ),
            model_used="fake",
            raw="{}",
            corrected=True,
        )


class SafetyRouter:
    def route(self, user_text: str) -> RouterResult:
        return RouterResult(
            decision=RouterDecision(
                intent="safety",
                domain="safety",
                action="confirm_before_action",
                route="safety_confirmation",
                risk_level="medium",
            ),
            model_used="fake",
            raw="{}",
            corrected=True,
        )


class FakeMainModel(MainModel):
    def respond(self, context):
        return "Respuesta chat"

    def respond_stream(self, context):
        yield "Res"
        yield "puesta"


class FakeActionModel(MainModel):
    def plan_or_act(self, context):
        return ModelAction(
            kind="tool_call",
            tool_call=ToolCall(
                tool_name="browser_search",
                arguments={"query": context.user_message, "target": "youtube"},
                risk_level="low",
            ),
        )


class FakeRagModel(MainModel):
    def respond_with_rag(self, context):
        return "Respuesta RAG"


class FakeRagRetriever:
    def retrieve(self, query):
        return [
            {
                "source": "agent/knowledge/docs/json.md",
                "text": "Procedimiento JSON local para tool calling.",
                "score": 0.9,
            }
        ]


class FakeToolPlanner:
    def plan(self, context):
        return ToolPlannerResult(
            model_used="fake-tool-planner",
            tool_calls=[
                ToolCall(
                    tool_name="browser_search",
                    arguments={"query": context.user_message, "target": "youtube"},
                    risk_level="low",
                )
            ],
        )


def make_gateway(tmp_path: Path, router, model, pipeline=None) -> Gateway:
    return Gateway(
        session_manager=SessionManager(store=SQLiteStore(tmp_path / "memory.db")),
        router=router,
        pipeline=pipeline,
        response_controller=ResponseController(
            main_model=model,
            tool_planner=FakeToolPlanner(),
        ),
        logger=GatewayLogger(tmp_path / "logs"),
    )


def latest_dev_event(tmp_path: Path) -> dict:
    path = tmp_path / "logs" / "dev_events.jsonl"
    return json.loads(path.read_text(encoding="utf-8").strip().splitlines()[-1])


def test_dev_event_builder_chat_summary():
    response = AgentResponse(
        session_id="s1",
        status="ok",
        text="hola",
        route="chat",
        debug={
            "router": {
                "decision": {"intent": "chat", "domain": "general", "action": "respond"},
                "model_used": "fake",
                "corrected": True,
                "raw": "{}",
            },
            "context": {
                "session_state": {"current_route": "chat"},
                "selected_plugins": [],
                "selected_skills": [],
                "selected_tools": [],
                "rag_snippets": [],
            },
        },
    )

    event = build_dev_event(response)

    assert event["status"] == "ok"
    assert event["route"] == "chat"
    assert event["session_id"] == "s1"
    assert event["router"]["intent"] == "chat"
    assert event["capabilities"]["tools"] == []
    assert event["rag"]["count"] == 0
    assert event["reflection"] is None


def test_dev_event_builder_action_ready_includes_tool_and_reflection():
    response = AgentResponse(
        session_id="s1",
        status="ok",
        text="done",
        route="action_ready",
        tool_calls=[
            {
                "tool_name": "browser_search",
                "arguments": {"query": "omega", "target": "youtube"},
                "risk_level": "low",
                "requires_confirmation": False,
            }
        ],
        debug={
            "tool_result": ToolResult(
                tool_name="browser_search",
                success=True,
                data={"query": "omega", "target": "youtube"},
            ).model_dump(mode="json"),
            "retry_count": 0,
            "retry_reason": "tool_success",
            "reflection": [
                {
                    "attempt_number": 0,
                    "execution_number": 1,
                    "tool_result": {"success": True},
                    "decision": {
                        "reason": "tool_success",
                        "should_retry": False,
                        "should_stop": False,
                    },
                }
            ],
        },
    )

    event = build_dev_event(response)

    assert event["tool_calls"][0]["tool_name"] == "browser_search"
    assert event["tool_result"]["success"] is True
    assert event["reflection"]["retry_count"] == 0
    assert event["reflection"]["attempts"][0]["decision_reason"] == "tool_success"


def test_gateway_writes_dev_event_after_chat(tmp_path):
    gateway = make_gateway(tmp_path, ChatRouter(), FakeMainModel())
    response = gateway.handle_message("hola")
    event = latest_dev_event(tmp_path)

    assert response.debug == {}
    assert event["route"] == "chat"
    assert event["status"] == "ok"
    assert event["router"]["intent"] == "chat"


def test_gateway_writes_dev_event_after_action_ready_tool_loop(tmp_path, monkeypatch):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    gateway = make_gateway(tmp_path, ActionRouter(), FakeActionModel())
    response = gateway.handle_message("busca omega en youtube")
    event = latest_dev_event(tmp_path)

    assert response.tool_calls
    assert event["route"] == "action_ready"
    assert event["tool_calls"][0]["tool_name"] == "browser_search"
    assert event["tool_result"]["success"] is True
    assert event["reflection"]["retry_count"] == 0


def test_gateway_writes_dev_event_after_rag_lookup(tmp_path):
    pipeline = Pipeline(ContextBuilder(rag_retriever=FakeRagRetriever()))
    gateway = make_gateway(tmp_path, RagRouter(), FakeRagModel(), pipeline=pipeline)
    gateway.handle_message("según mis notas sobre JSON")
    event = latest_dev_event(tmp_path)

    assert event["route"] == "rag_lookup"
    assert event["rag"]["count"] == 1
    assert event["rag"]["sources"] == ["agent/knowledge/docs/json.md"]
    assert event["tool_calls"] == []


def test_gateway_writes_dev_event_after_safety_confirmation(tmp_path):
    gateway = make_gateway(tmp_path, SafetyRouter(), FakeMainModel())
    gateway.handle_message("borra esos archivos")
    event = latest_dev_event(tmp_path)

    assert event["route"] == "safety_confirmation"
    assert event["needs_user_input"] is True
    assert event["session_state"]["pending_confirmation"] == {
        "message": "borra esos archivos"
    }
    assert event["router"]["risk_level"] == "medium"


def test_streaming_writes_one_dev_event_after_final(tmp_path):
    gateway = make_gateway(tmp_path, ChatRouter(), FakeMainModel())
    events = list(gateway.stream_message("hola"))
    lines = (tmp_path / "logs" / "dev_events.jsonl").read_text(encoding="utf-8").splitlines()

    assert [event["type"] for event in events if event["type"] == "token"] == ["token", "token"]
    assert len(lines) == 1
    assert json.loads(lines[0])["status"] == "ok"


def test_streaming_error_writes_dev_event(tmp_path):
    class FailingStreamModel(FakeMainModel):
        def respond_stream(self, context):
            yield "partial"
            raise RuntimeError("stream unavailable")

    gateway = make_gateway(tmp_path, ChatRouter(), FailingStreamModel())
    events = list(gateway.stream_message("hola"))
    event = latest_dev_event(tmp_path)

    assert any(item["type"] == "error" for item in events)
    assert event["status"] == "error"
    assert event["route"] == "chat"


def test_dev_console_reader_tail_filter_and_corrupt_lines(tmp_path):
    path = tmp_path / "dev_events.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"session_id": "a", "route": "chat"}),
                "not-json",
                json.dumps({"session_id": "b", "route": "rag_lookup"}),
            ]
        ),
        encoding="utf-8",
    )

    events, warnings = read_dev_events(path, session_id="b", tail=1)

    assert events == [{"session_id": "b", "route": "rag_lookup"}]
    assert warnings == ["Skipped corrupt JSONL line 2."]


def test_dev_console_missing_file_message(tmp_path):
    events, warnings = read_dev_events(tmp_path / "missing.jsonl")
    assert events == []
    assert "No dev events log found" in warnings[0]


def test_dev_console_cli_renders_tail_json_and_filter(tmp_path):
    path = tmp_path / "dev_events.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"session_id": "a", "status": "ok", "route": "chat"}),
                json.dumps({"session_id": "b", "status": "ok", "route": "rag_lookup"}),
            ]
        ),
        encoding="utf-8",
    )
    rendered = []
    raw = []

    run_dev_console(path=path, session_id="b", tail=5, output_func=rendered.append)
    run_dev_console(path=path, json_output=True, tail=1, output_func=raw.append)

    assert "route: rag_lookup" in rendered[0]
    assert raw == [{"session_id": "b", "status": "ok", "route": "rag_lookup"}]


def test_dev_console_renders_early_ack_event(tmp_path):
    path = tmp_path / "dev_events.jsonl"
    path.write_text(
        json.dumps(
            {
                "type": "early_ack",
                "session_id": "s1",
                "text": "Claro, voy a buscarlo ahora.",
                "route": "action_ready",
                "suggested_tools": ["browser_search"],
            }
        ),
        encoding="utf-8",
    )

    rendered = []
    run_dev_console(path=path, tail=1, output_func=rendered.append)

    assert "status: early_ack" in rendered[0]
    assert "Claro, voy a buscarlo ahora." in rendered[0]
    assert "browser_search" in rendered[0]


def test_dev_console_renders_model_changed_event(tmp_path):
    path = tmp_path / "dev_events.jsonl"
    path.write_text(
        json.dumps(
            {
                "type": "model_changed",
                "role": "main",
                "model": "llama3.1:8b",
            }
        ),
        encoding="utf-8",
    )

    rendered = []
    run_dev_console(path=path, tail=1, output_func=rendered.append)

    assert "status: model_changed" in rendered[0]
    assert "role: main" in rendered[0]
    assert "model: llama3.1:8b" in rendered[0]


def test_follow_missing_file_does_not_crash(tmp_path):
    output = []
    run_dev_console(
        path=tmp_path / "missing.jsonl",
        follow=True,
        stop_after=1,
        output_func=output.append,
    )
    assert "No dev events log found" in output[0]


def test_repl_stream_remains_clean_without_internal_logs():
    class CleanGateway:
        def __init__(self):
            self.sessions = type("Sessions", (), {"get_or_create": lambda _s, _id=None: None})()

        def stream_message(self, message, session_id=None, debug=False):
            yield {"type": "token", "text": "Hola"}
            yield {
                "type": "final",
                "response": AgentResponse(
                    session_id="s1", status="ok", text="Hola", route="chat"
                ),
            }

    output = []
    prompts = iter(["hola", "/exit"])

    run_repl(
        CleanGateway(),
        stream=True,
        input_func=lambda _prompt: next(prompts),
        output_func=lambda message, **_kwargs: output.append(str(message)),
    )

    assert not any("router" in item or "context" in item for item in output)
