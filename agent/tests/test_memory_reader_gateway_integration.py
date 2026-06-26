from pathlib import Path

from agent.gateway.gateway import Gateway
from agent.gateway.gateway_logger import GatewayLogger
from agent.gateway.session_manager import SessionManager
from agent.gateway.message_types import AgentResponse
from agent.memory.learning_memory import record_learning_memory
from agent.memory.sqlite_store import SQLiteStore
from agent.router.router_schema import RouterDecision, RouterResult


class ChatRouter:
    def route(self, user_text: str):
        return RouterResult(
            decision=RouterDecision(
                intent="chat",
                domain="general",
                action="respond",
                route="chat",
                needs_tool=False,
            ),
            model_used="fake-router",
            raw="{}",
            corrected=False,
        )


class CapturingResponseController:
    def __init__(self):
        self.contexts = []

    def handle(self, context, session, debug=False):
        self.contexts.append(context)

        return AgentResponse(
            session_id=session.session_id,
            status="ok",
            text="ok",
            route=context.router_decision.route,
            debug={"context": context.model_dump(mode="json")} if debug else {},
        )


def test_gateway_default_pipeline_injects_learning_hints(tmp_path: Path):
    store = SQLiteStore(tmp_path / "memory.db")

    for _ in range(2):
        record_learning_memory(
            store,
            user_phrase="abre figma",
            correct_intent="action",
            correct_tool="open_app",
            correct_skill="open_app",
            status="temporary",
            confidence=0.65,
        )

    controller = CapturingResponseController()

    gateway = Gateway(
        session_manager=SessionManager(store=store),
        router=ChatRouter(),
        response_controller=controller,
        logger=GatewayLogger(tmp_path / "logs"),
    )

    response = gateway.handle_message("abre figma", debug=True)

    assert response.status == "ok"
    assert controller.contexts

    hints = controller.contexts[0].session_state["learning_hints"]

    assert len(hints) == 1
    assert hints[0]["status"] == "candidate"
    assert hints[0]["correct_tool"] == "open_app"
    assert hints[0]["correct_skill"] == "open_app"


def test_gateway_learning_hints_do_not_execute_or_change_route(tmp_path: Path):
    store = SQLiteStore(tmp_path / "memory.db")

    for _ in range(2):
        record_learning_memory(
            store,
            user_phrase="abre figma",
            correct_intent="action",
            correct_tool="open_app",
            correct_skill="open_app",
            status="temporary",
            confidence=0.65,
        )

    controller = CapturingResponseController()

    gateway = Gateway(
        session_manager=SessionManager(store=store),
        router=ChatRouter(),
        response_controller=controller,
        logger=GatewayLogger(tmp_path / "logs"),
    )

    response = gateway.handle_message("abre figma", debug=True)

    assert response.route == "chat"
    assert response.tool_calls == []

    # La fuente de verdad para este test es el ContextPackage recibido por
    # ResponseController. response.debug puede ser mergeado/procesado luego por Gateway.
    hints = controller.contexts[0].session_state["learning_hints"]

    assert hints[0]["correct_tool"] == "open_app"
    assert hints[0]["correct_skill"] == "open_app"
