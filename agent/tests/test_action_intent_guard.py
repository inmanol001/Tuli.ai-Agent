from agent.action_guard.intent_guard import ActionIntentGuard
from agent.gateway.message_types import ContextPackage
from agent.router.router_schema import RouterDecision


def make_context(message: str, route: str = "chat") -> ContextPackage:
    return ContextPackage(
        system_prompt="system",
        user_message=message,
        router_decision=RouterDecision(route=route),
    )


def test_open_target_is_action_required():
    result = ActionIntentGuard().evaluate(make_context("abre Figma"))
    assert result.action_required is True
    assert result.suggested_route == "action_ready"
    assert result.action_type == "open"
    assert result.target == "Figma"


def test_show_target_is_action_required():
    result = ActionIntentGuard().evaluate(make_context("muéstrame Google"))
    assert result.action_required is True
    assert result.suggested_route == "action_ready"
    assert result.action_type == "show"
    assert result.target == "Google"


def test_take_me_to_target_is_action_required():
    result = ActionIntentGuard().evaluate(make_context("llévame a GitHub"))
    assert result.action_required is True
    assert result.suggested_route == "action_ready"
    assert result.action_type == "show"
    assert result.target == "GitHub"


def test_window_move_is_action_required():
    result = ActionIntentGuard().evaluate(make_context("pon la ventana a la izquierda"))
    assert result.action_required is True
    assert result.suggested_route == "action_ready"
    assert result.action_type == "window_move"
    assert "ventana" in result.target.lower()


def test_activate_mission_control_is_action_required():
    result = ActionIntentGuard().evaluate(make_context("activa Mission Control"))
    assert result.action_required is True
    assert result.suggested_route == "action_ready"
    assert result.action_type == "activate"
    assert result.target == "Mission Control"


def test_search_target_is_action_required():
    result = ActionIntentGuard().evaluate(make_context("busca documentación de Ollama"))
    assert result.action_required is True
    assert result.suggested_route == "action_ready"
    assert result.action_type == "search"
    assert result.target == "documentación de Ollama"


def test_conceptual_question_stays_chat():
    result = ActionIntentGuard().evaluate(make_context("qué es Google"))
    assert result.action_required is False
    assert result.suggested_route == "chat"
    assert result.reason == "conceptual_question"


def test_missing_target_needs_clarification():
    result = ActionIntentGuard().evaluate(make_context("abre"))
    assert result.action_required is False
    assert result.suggested_route == "clarification"
    assert result.missing_info == ["target"]


def test_vague_reference_is_not_action_intent_guard_responsibility():
    result = ActionIntentGuard().evaluate(make_context("ábrela"))
    assert result.action_required is False
    assert result.suggested_route == "chat"
    assert result.reason == "no_action_pattern"


def test_route_not_chat_is_ignored():
    result = ActionIntentGuard().evaluate(make_context("abre Figma", route="action_ready"))
    assert result.action_required is False
    assert result.reason == "route_not_chat"
