import json

from agent.clarification.builder import ClarificationBuilder
from agent.clarification.chat_guard import ChatSafetyClarificationGuard
from agent.gateway.gateway import Gateway
from agent.gateway.gateway_logger import GatewayLogger
from agent.gateway.message_types import ContextPackage, ConversationTurn
from agent.gateway.session_manager import SessionState
from agent.router.router_schema import RouterDecision, RouterResult
from agent.response_action.controller import ResponseController
from agent.tests.test_gateway import FakeMainModel, FakeRouter
from agent.tests.test_behavior import FakeClient


def make_context(user_message: str) -> ContextPackage:
    return ContextPackage(
        system_prompt="system",
        user_message=user_message,
        router_decision=RouterDecision(route="chat"),
        session_state={},
    )


def test_chat_guard_flags_vague_open_reference():
    guard = ChatSafetyClarificationGuard()
    result = guard.evaluate(make_context("abre la que te mencioné ahorita"))

    assert result.should_clarify is True
    assert result.pending_clarification == "target_url"
    assert "target_url" in result.missing_info or "missing_details" in result.missing_info


def test_chat_guard_flags_status_question():
    guard = ChatSafetyClarificationGuard()
    result = guard.evaluate(make_context("se aplicó el cambio?"))

    assert result.should_clarify is True
    assert result.pending_clarification == "tool_result"
    assert "tool_result" in result.missing_info


def test_chat_guard_leaves_conceptual_question_alone():
    guard = ChatSafetyClarificationGuard()
    result = guard.evaluate(make_context("explícame la diferencia entre router y guard"))

    assert result.should_clarify is False


def test_chat_guard_leaves_simple_conceptual_question_alone():
    guard = ChatSafetyClarificationGuard()
    result = guard.evaluate(make_context("qué es Canva?"))

    assert result.should_clarify is False


def test_chat_guard_leaves_greeting_alone():
    guard = ChatSafetyClarificationGuard()
    result = guard.evaluate(make_context("hola Tuli"))

    assert result.should_clarify is False


def test_chat_guard_resolves_single_vague_reference_from_history():
    guard = ChatSafetyClarificationGuard()
    context = ContextPackage(
        system_prompt="system",
        user_message="ábrela",
        router_decision=RouterDecision(route="chat"),
        recent_history=[ConversationTurn(role="user", content="vamos a trabajar con Canva")],
    )

    result = guard.evaluate(context)

    assert result.should_clarify is True
    assert result.reason == "resolved_reference_confirmation"
    assert result.pending_clarification == "resolved_reference_confirmation"
    assert result.resolved_reference == "Canva"


def test_chat_guard_flags_ambiguous_reference_from_history():
    guard = ChatSafetyClarificationGuard()
    context = ContextPackage(
        system_prompt="system",
        user_message="ábrela",
        router_decision=RouterDecision(route="chat"),
        recent_history=[
            ConversationTurn(role="user", content="tenemos dos opciones: Canva y GitHub")
        ],
    )

    result = guard.evaluate(context)

    assert result.should_clarify is True
    assert result.pending_clarification == "ambiguous_reference"
    assert "Canva" in result.candidates
    assert "GitHub" in result.candidates
    assert result.reason == "ambiguous_reference"


def test_chat_guard_recent_tool_result_unblocks_status_question():
    guard = ChatSafetyClarificationGuard()
    context = ContextPackage(
        system_prompt="system",
        user_message="quedó abierta?",
        router_decision=RouterDecision(route="chat"),
        recent_history=[
            ConversationTurn(
                role="tool",
                content=(
                    '{"tool_name":"browser_search","success":true,'
                    '"data":{"url":"https://github.com","query":"github"}}'
                ),
            )
        ],
    )

    result = guard.evaluate(context)

    assert result.should_clarify is False
    assert result.reason == "recent_tool_result_available"
    assert result.context_resolution is not None


def test_chat_guard_status_question_without_tool_result_needs_clarification():
    guard = ChatSafetyClarificationGuard()
    result = guard.evaluate(make_context("se aplicó el cambio?"))

    assert result.should_clarify is True
    assert result.pending_clarification == "tool_result"
    assert result.reason == "missing_recent_tool_result"


def test_chat_guard_explicit_platform_missing_content_needs_clarification():
    guard = ChatSafetyClarificationGuard()
    result = guard.evaluate(make_context("monta ese texto en Canva"))

    assert result.should_clarify is True
    assert result.reason == "explicit_platform_missing_content"
    assert result.pending_clarification == "target_content"


def test_chat_guard_flags_error_fix_request():
    guard = ChatSafetyClarificationGuard()
    result = guard.evaluate(make_context("corrige la parte que falla"))

    assert result.should_clarify is True
    assert result.pending_clarification == "target_file_or_error"


def test_clarification_builder_supports_new_missing_info_keys():
    builder = ClarificationBuilder()
    result = builder.build(
        ContextPackage(
            system_prompt="system",
            user_message="se aplicó el cambio?",
            router_decision=RouterDecision(route="clarification", missing_info=["tool_result"]),
            session_state={"pending_clarification": "tool_result"},
        ),
        missing_info_override=["tool_result"],
        reason_hint="status_question",
    )

    assert "resultado reciente de una herramienta" in result.text
    assert result.pending_clarification == "tool_result"


def test_gateway_routes_status_question_to_clarification(tmp_path):
    gateway = Gateway(
        router=FakeRouter(),
        response_controller=ResponseController(main_model=FakeMainModel()),
        logger=GatewayLogger(tmp_path / "logs"),
    )

    response = gateway.handle_message("se aplicó el cambio?", debug=True)

    assert response.status == "needs_clarification"
    assert response.route == "clarification"
    assert "chat_clarification_guard" in response.debug
    assert "clarification" in response.debug
    assert "sí" not in response.text.lower()


def test_gateway_answers_recent_tool_result_status_directly(tmp_path):
    gateway = Gateway(
        router=FakeRouter(),
        response_controller=ResponseController(main_model=FakeMainModel()),
        logger=GatewayLogger(tmp_path / "logs"),
    )
    session = gateway.sessions.get_or_create()
    gateway.sessions.add_turn_with_metadata(
        session.session_id,
        "tool",
        json.dumps(
            {
                "tool_name": "browser_search",
                "success": True,
                "data": {"url": "https://github.com", "query": "github", "opened": True},
            }
        ),
    )

    response = gateway.handle_message("quedó abierta?", session_id=session.session_id, debug=True)

    assert response.status == "ok"
    assert response.route == "chat"
    assert "https://github.com" in response.text
    assert "no tengo un `tool_result` reciente" not in response.text.lower()
    assert response.debug["chat_clarification_guard"]["reason"] == "recent_tool_result_available"
    assert response.debug["context_resolution"]["reason"] == "recent_tool_result_available"


def test_gateway_keeps_conceptual_question_in_chat(tmp_path):
    gateway = Gateway(
        router=FakeRouter(),
        response_controller=ResponseController(main_model=FakeMainModel()),
        logger=GatewayLogger(tmp_path / "logs"),
    )

    response = gateway.handle_message("explícame la diferencia entre router y guard", debug=True)

    assert response.status == "ok"
    assert response.route == "chat"
    assert "chat_clarification_guard" not in response.debug or response.debug["chat_clarification_guard"]["should_clarify"] is False


def test_gateway_routes_vague_open_reference_to_clarification(tmp_path):
    gateway = Gateway(
        router=FakeRouter(),
        response_controller=ResponseController(main_model=FakeMainModel()),
        logger=GatewayLogger(tmp_path / "logs"),
    )

    response = gateway.handle_message("abre la que te mencioné ahorita", debug=True)

    assert response.status == "needs_clarification"
    assert response.route == "clarification"
    assert "1." in response.text
    assert "chat_clarification_guard" in response.debug
    assert response.debug["chat_clarification_guard"]["should_clarify"] is True


def test_gateway_routes_explicit_platform_missing_content_to_clarification(tmp_path):
    gateway = Gateway(
        router=FakeRouter(),
        response_controller=ResponseController(main_model=FakeMainModel()),
        logger=GatewayLogger(tmp_path / "logs"),
    )

    response = gateway.handle_message("monta ese texto en Canva", debug=True)

    assert response.status == "needs_clarification"
    assert response.route == "clarification"
    assert "Canva" in response.text
    assert "qué contenido" in response.text.lower()
    assert "Entiendo que te refieres a Canva" not in response.text
    assert response.debug["chat_clarification_guard"]["reason"] == "explicit_platform_missing_content"
    assert response.debug["clarification"]["pending_clarification"] == "target_content"


def test_gateway_resolves_single_vague_reference_from_history(tmp_path):
    gateway = Gateway(
        router=FakeRouter(),
        response_controller=ResponseController(main_model=FakeMainModel()),
        logger=GatewayLogger(tmp_path / "logs"),
    )

    first = gateway.handle_message("vamos a trabajar con Canva")
    second = gateway.handle_message("ábrela", session_id=first.session_id, debug=True)

    assert second.route == "chat"
    assert second.status == "ok"
    assert second.debug["chat_clarification_guard"]["resolved_reference"] == "Canva"
    assert second.debug["chat_clarification_guard"]["should_clarify"] is False


def test_gateway_flags_ambiguous_reference_from_history(tmp_path):
    gateway = Gateway(
        router=FakeRouter(),
        response_controller=ResponseController(main_model=FakeMainModel()),
        logger=GatewayLogger(tmp_path / "logs"),
    )

    first = gateway.handle_message("tenemos dos opciones: Canva y GitHub")
    second = gateway.handle_message("ábrela", session_id=first.session_id, debug=True)

    assert second.status == "needs_clarification"
    assert second.route == "clarification"
    assert "Canva" in second.debug["chat_clarification_guard"]["candidates"]
    assert "GitHub" in second.debug["chat_clarification_guard"]["candidates"]


def test_gateway_routes_error_fix_request_to_clarification(tmp_path):
    gateway = Gateway(
        router=FakeRouter(),
        response_controller=ResponseController(main_model=FakeMainModel()),
        logger=GatewayLogger(tmp_path / "logs"),
    )

    response = gateway.handle_message("corrige la parte que falla", debug=True)

    assert response.status == "needs_clarification"
    assert response.route == "clarification"
    assert response.debug["chat_clarification_guard"]["pending_clarification"] == "target_file_or_error"
    assert "archivo" in response.text.lower() or "error" in response.text.lower()
    assert "parte" in response.text.lower() or "revisar" in response.text.lower()


def test_gateway_routes_canva_ambiguity_to_clarification(tmp_path):
    gateway = Gateway(
        router=FakeRouter(),
        response_controller=ResponseController(main_model=FakeMainModel()),
        logger=GatewayLogger(tmp_path / "logs"),
    )

    response = gateway.handle_message("monta ese texto en Canva", debug=True)

    assert response.status == "needs_clarification"
    assert response.route == "clarification"
    assert "qué contenido" in response.text.lower()
    assert "diseño" in response.text.lower() or "plataforma" in response.text.lower()
