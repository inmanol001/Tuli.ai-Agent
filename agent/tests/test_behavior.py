from pathlib import Path

from agent.behavior.loader import get_soul_prompt, load_soul
from agent.context_builder.assembler import assemble_messages
from agent.context_builder.builder import ContextBuilder
from agent.gateway.gateway import Gateway
from agent.gateway.gateway_logger import GatewayLogger
from agent.gateway.message_types import ContextPackage
from agent.gateway.session_manager import SessionState
from agent.models.main_model import MainModel
from agent.models.tool_planner import ToolPlanner
from agent.router.router_schema import RouterDecision
from agent.response_action.controller import ResponseController


class FakeChatRouter:
    def route(self, user_text: str):
        from agent.router.router_schema import RouterDecision, RouterResult

        return RouterResult(
            decision=RouterDecision(route="chat"),
            model_used="fake",
            raw="{}",
            corrected=True,
        )


class FakeClient:
    def __init__(self):
        self.calls = []

    def chat(self, model, messages, **kwargs):
        self.calls.append((model, list(messages), kwargs))
        return "hola"


class FakeChatModel(MainModel):
    def __init__(self, client):
        super().__init__(client=client)


def test_main_model_respond_includes_soul_in_messages():
    client = FakeClient()
    model = MainModel(client=client)
    context = ContextPackage(
        system_prompt="system",
        user_message="hola",
        router_decision=RouterDecision(route="chat"),
    )

    model.respond(context)

    sent_messages = client.calls[0][1]
    joined = "\n".join(message["content"] for message in sent_messages)
    assert "SOUL de Tuli" in joined
    assert sent_messages[0]["role"] == "system"
    assert sent_messages[1]["role"] == "system"


def test_gateway_chat_debug_includes_soul(tmp_path):
    gateway = Gateway(
        router=FakeChatRouter(),
        response_controller=ResponseController(main_model=FakeChatModel(FakeClient())),
        logger=GatewayLogger(tmp_path / "logs"),
    )

    response = gateway.handle_message("hola", debug=True)

    assert response.route == "chat"
    assert response.debug["soul"]["loaded"] is True
    assert response.debug["soul"]["fallback_used"] is False
    assert response.debug["soul"]["chars"] > 0


def _chat_context() -> ContextPackage:
    return ContextPackage(
        system_prompt="system",
        user_message="hola",
        router_decision=RouterDecision(route="chat"),
        behavior={
            "soul_loaded": True,
            "soul_source": "agent/behavior/SOUL.md",
            "soul_fallback_used": False,
            "soul_error": None,
        },
    )


def test_soul_markdown_exists():
    assert Path("agent/behavior/SOUL.md").exists()


def test_soul_loader_reads_soul_markdown():
    load_soul.cache_clear()
    soul = load_soul()

    assert soul.loaded is True
    assert soul.fallback_used is False
    assert "SOUL de Tuli" in soul.content
    assert get_soul_prompt() == soul.content


def test_chat_prompt_includes_soul_but_tool_planner_does_not():
    context = ContextBuilder().build(
        "hola",
        RouterDecision(route="chat"),
        SessionState(session_id="s1"),
    )
    chat_messages = assemble_messages(context)
    planner_messages = ToolPlanner()._messages(context)

    joined_chat = "\n".join(message["content"] for message in chat_messages)
    joined_planner = "\n".join(message["content"] for message in planner_messages)

    assert "SOUL de Tuli" in joined_chat
    assert "Tuli soul:" in joined_chat
    assert "SOUL de Tuli" not in joined_planner
    assert "Tuli soul:" not in joined_planner


def test_context_builder_exposes_soul_debug_metadata():
    context = ContextBuilder().build(
        "hola",
        RouterDecision(route="chat"),
        SessionState(session_id="s1"),
    )

    assert context.behavior["soul_loaded"] is True
    assert context.behavior["soul_source"].endswith("agent/behavior/SOUL.md")
    assert context.behavior["soul_fallback_used"] is False


def test_loader_falls_back_when_soul_file_is_missing(monkeypatch, tmp_path):
    from agent.behavior import loader as soul_loader

    monkeypatch.setattr(soul_loader, "SOUL_PATH", tmp_path / "missing" / "SOUL.md")
    soul_loader.load_soul.cache_clear()

    soul = soul_loader.load_soul()

    assert soul.loaded is False
    assert soul.fallback_used is True
    assert "SOUL.md not found" in (soul.error or "")
    assert "local agent" in soul.content


def test_gateway_chat_debug_uses_soul_fallback_when_missing(monkeypatch, tmp_path):
    from agent.behavior import loader as soul_loader

    monkeypatch.setattr(soul_loader, "SOUL_PATH", tmp_path / "missing" / "SOUL.md")
    soul_loader.load_soul.cache_clear()

    gateway = Gateway(
        router=FakeChatRouter(),
        response_controller=ResponseController(main_model=FakeChatModel(FakeClient())),
        logger=GatewayLogger(tmp_path / "logs2"),
    )

    response = gateway.handle_message("hola", debug=True)

    assert response.debug["soul"]["loaded"] is False
    assert response.debug["soul"]["fallback_used"] is True
    assert response.debug["soul"]["error"] is not None
