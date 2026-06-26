import pytest

from agent.gateway.gateway import Gateway
from agent.gateway.gateway_logger import GatewayLogger
from agent.gateway.message_types import ContextPackage
from agent.gateway.pipeline import Pipeline
from agent.context_builder.builder import ContextBuilder
from agent.models.action_models import ModelAction
from agent.capabilities.tools.schemas import ToolCall
from agent.gateway.session_manager import SessionManager
from agent.memory.sqlite_store import SQLiteStore
from agent.models.main_model import MainModel
from agent.models.ollama_client import OllamaClient
from agent.models.tool_planner import ToolPlannerResult
from agent.response_action.controller import ResponseController
from agent.router.router_schema import RouterDecision, RouterResult


class FakeChatRouter:
    def route(self, user_text: str) -> RouterResult:
        return RouterResult(
            decision=RouterDecision(route="chat"),
            model_used="fake",
            raw="{}",
            corrected=True,
        )


class FakeStreamingModel(MainModel):
    def __init__(self, chunks=None, fail_after_first=False):
        self.chunks = chunks or ["Ho", "la"]
        self.fail_after_first = fail_after_first

    def respond_stream(self, context):
        for index, chunk in enumerate(self.chunks):
            if index == 1 and self.fail_after_first:
                raise RuntimeError("stream connection unavailable")
            yield chunk

    def respond(self, context):
        return "".join(self.chunks)


class FakeActionRouter:
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


class FakeClarificationRouter:
    def route(self, user_text: str) -> RouterResult:
        return RouterResult(
            decision=RouterDecision(
                intent="action",
                domain="browser",
                action="search",
                route="clarification",
                needs_tool=True,
                needs_clarification=True,
                missing_info=["search_query"],
                suggested_plugins=["browser"],
                suggested_skills=["browser_search"],
                suggested_tools=["browser_search"],
            ),
            model_used="fake",
            raw="{}",
            corrected=True,
        )


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

    def respond_stream(self, context):
        raise AssertionError("action_ready must not stream")


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


class FakeRagRouter:
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


class EmptyRagRetriever:
    def retrieve(self, query):
        return []


class FakeOllamaResponse:
    class Message:
        content = "normal"

    message = Message()


def test_ollama_client_chat_stream_yields_chunks(monkeypatch):
    def fake_chat(**kwargs):
        assert kwargs["stream"] is True
        return [
            {"message": {"content": "Ho"}},
            {"message": {"content": "la"}},
        ]

    monkeypatch.setattr("agent.models.ollama_client.ollama.chat", fake_chat)

    chunks = list(OllamaClient().chat_stream("qwen3:4b", [{"role": "user", "content": "hola"}]))

    assert chunks == ["Ho", "la"]


def test_ollama_client_chat_stream_filters_thinking(monkeypatch):
    def fake_chat(**kwargs):
        assert kwargs["stream"] is True
        return [
            {"message": {"content": "thinking..."}},
            {"message": {"content": "</think>"}},
            {"message": {"content": "¡"}},
            {"message": {"content": "Hola"}},
            {"message": {"content": "!"}},
        ]

    monkeypatch.setattr("agent.models.ollama_client.ollama.chat", fake_chat)

    chunks = list(OllamaClient().chat_stream("qwen3:4b", [{"role": "user", "content": "hola"}]))

    assert chunks == ["¡", "Hola", "!"]
    assert "".join(chunks) == "¡Hola!"


def test_ollama_client_chat_stream_rejects_format_schema():
    with pytest.raises(ValueError):
        list(
            OllamaClient().chat_stream(
                "qwen3:4b",
                [{"role": "user", "content": "hola"}],
                format_schema={"type": "object"},
            )
        )


def test_main_model_respond_stream_uses_client_stream():
    class FakeClient:
        def __init__(self):
            self.calls = []

        def chat_stream(self, model, messages, **kwargs):
            self.calls.append((model, list(messages), kwargs))
            yield "A"
            yield "B"

    client = FakeClient()
    model = MainModel(client=client)

    context = ContextPackage(
        system_prompt="system",
        user_message="hola",
        router_decision=RouterDecision(route="chat"),
    )
    chunks = list(model.respond_stream(context))

    assert chunks == ["A", "B"]
    assert client.calls[0][2]["options"]["temperature"] == 0.3


def make_stream_gateway(tmp_path, model):
    return Gateway(
        router=FakeChatRouter(),
        response_controller=ResponseController(main_model=model),
        logger=GatewayLogger(tmp_path / "logs"),
    )


def test_gateway_stream_message_chat_emits_tokens_and_final(tmp_path):
    gateway = make_stream_gateway(tmp_path, FakeStreamingModel(["Ho", "la"]))

    events = list(gateway.stream_message("hola", debug=True))
    final = events[-2]["response"]

    assert [event["text"] for event in events if event["type"] == "token"] == ["Ho", "la"]
    assert events[-2]["type"] == "final"
    assert events[-1]["type"] == "debug"
    assert final.text == "Hola"
    stored = gateway.sessions.get_or_create(final.session_id)
    assert len([turn for turn in stored.history if turn.role == "assistant"]) == 1
    assert stored.history[-1].content == "Hola"


def test_gateway_stream_message_skips_empty_tokens_and_keeps_visible_text(tmp_path):
    gateway = make_stream_gateway(
        tmp_path,
        FakeStreamingModel(["", "¡", "", "Hola", "!", ""]),
    )

    events = list(gateway.stream_message("hola", debug=True))
    tokens = [event["text"] for event in events if event["type"] == "token"]
    final = [event["response"] for event in events if event["type"] == "final"][0]

    assert tokens == ["¡", "Hola", "!"]
    assert "" not in tokens
    assert final.text == "¡Hola!"
    assert "thinking" not in final.text
    assert "</think>" not in final.text


def test_gateway_stream_message_failure_does_not_save_partial_assistant(tmp_path):
    gateway = make_stream_gateway(
        tmp_path,
        FakeStreamingModel(["Ho", "la"], fail_after_first=True),
    )

    events = list(gateway.stream_message("hola", debug=True))
    error_response = [event["response"] for event in events if event["type"] == "error"][0]
    stored = gateway.sessions.get_or_create(error_response.session_id)

    assert error_response.status == "error"
    assert "stream connection unavailable" in error_response.text
    assert [turn for turn in stored.history if turn.role == "assistant"] == []
    with gateway.sessions.store.connect() as conn:
        row = conn.execute(
            "SELECT * FROM error_memory WHERE error LIKE ? ORDER BY updated_at DESC LIMIT 1",
            ("%stream connection unavailable%",),
        ).fetchone()
    assert row is not None
    assert "stream connection unavailable" in row["error"]


def test_gateway_stream_message_action_ready_delegates_without_tokens(tmp_path):
    gateway = Gateway(
        router=FakeActionRouter(),
        response_controller=ResponseController(
            main_model=FakeActionModel(),
            tool_planner=FakeToolPlanner(),
        ),
        logger=GatewayLogger(tmp_path / "logs"),
    )

    events = list(gateway.stream_message("busca omega en youtube", debug=True))

    assert [event for event in events if event["type"] == "token"] == []
    assert events[0]["type"] == "early_ack"
    assert events[1]["type"] == "final"
    assert events[1]["response"].route == "action_ready"
    assert events[1]["response"].tool_calls[0]["tool_name"] == "browser_search"


def test_gateway_stream_message_chat_does_not_emit_early_ack(tmp_path):
    gateway = make_stream_gateway(tmp_path, FakeStreamingModel(["Ho", "la"]))

    events = list(gateway.stream_message("hola", debug=True))

    assert [event for event in events if event["type"] == "early_ack"] == []


def test_gateway_stream_message_clarification_does_not_emit_early_ack(tmp_path):
    gateway = Gateway(
        router=FakeClarificationRouter(),
        response_controller=ResponseController(
            main_model=FakeActionModel(),
            tool_planner=FakeToolPlanner(),
        ),
        logger=GatewayLogger(tmp_path / "logs"),
    )

    events = list(gateway.stream_message("busca música en YouTube", debug=True))

    assert [event for event in events if event["type"] == "early_ack"] == []
    assert events[0]["type"] == "final"
    assert events[0]["response"].route == "clarification"


def test_gateway_stream_message_rag_lookup_delegates_without_tokens(tmp_path):
    gateway = Gateway(
        router=FakeRagRouter(),
        pipeline=Pipeline(ContextBuilder(rag_retriever=EmptyRagRetriever())),
        response_controller=ResponseController(main_model=FakeStreamingModel()),
        logger=GatewayLogger(tmp_path / "logs"),
    )

    events = list(gateway.stream_message("según mis notas sobre JSON", debug=True))

    assert [event for event in events if event["type"] == "token"] == []
    assert events[0]["type"] == "final"
    assert events[0]["response"].route == "rag_lookup"
    assert events[0]["response"].tool_calls == []


def test_gateway_stream_message_chat_route_action_guard_recovery_does_not_stream(tmp_path):
    from agent.gateway.gateway import Gateway
    from agent.gateway.gateway_logger import GatewayLogger
    from agent.gateway.session_manager import SessionManager
    from agent.models.main_model import MainModel
    from agent.models.tool_planner import ToolPlannerResult
    from agent.response_action.controller import ResponseController
    from agent.executor.results import ToolResult

    class ExplodingStreamingModel(MainModel):
        def respond(self, context):
            raise AssertionError("respond no debe ser llamado para acción recuperada")

        def respond_stream(self, context):
            raise AssertionError("respond_stream no debe ser llamado para acción recuperada")
            yield ""

    class NoToolPlanner:
        def plan(self, context):
            return ToolPlannerResult(
                model_used="fake",
                content="no tool",
                tool_calls=[],
                raw={"fake": True},
                no_tool_reason="no_native_tool_call",
            )

    class CapturingExecutor:
        def __init__(self):
            self.calls = []

        def execute(self, call):
            self.calls.append(call)
            return ToolResult(
                tool_name=call.tool_name,
                success=True,
                data=dict(call.arguments),
                metadata={"test": True},
            )

    executor = CapturingExecutor()
    gateway = Gateway(
        response_controller=ResponseController(
            main_model=ExplodingStreamingModel(),
            tool_planner=NoToolPlanner(),
            executor=executor,
        ),
        logger=GatewayLogger(tmp_path / "logs"),
    )

    events = list(gateway.stream_message("abre Figma", debug=True))

    assert [event for event in events if event["type"] == "token"] == []
    final = [event["response"] for event in events if event["type"] == "final"][0]

    assert final.route == "action_ready"
    assert executor.calls
    assert executor.calls[0].tool_name == "open_app"
    assert executor.calls[0].arguments == {"app_name": "Figma"}
    assert final.debug["action_guard_recovered"] is True
    assert final.debug["tool_planner_fallback"] == "action_guard_open_app"


def test_gateway_stream_message_chat_still_streams_real_chat_after_guards(tmp_path):
    gateway = make_stream_gateway(tmp_path, FakeStreamingModel(["Ho", "la"]))

    events = list(gateway.stream_message("hola", debug=True))
    tokens = [event["text"] for event in events if event["type"] == "token"]
    final = [event["response"] for event in events if event["type"] == "final"][0]

    assert tokens == ["Ho", "la"]
    assert final.route == "chat"
    assert final.text == "Hola"
    assert final.debug["action_intent_guard"]["reason"] == "no_action_pattern"
