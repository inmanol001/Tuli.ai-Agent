from agent.gateway.gateway import Gateway
from agent.models.main_model import MainModel
from agent.response_action.controller import ResponseController


class ExplodingMainModel(MainModel):
    def respond(self, context):
        raise AssertionError("MainModel no debe ser llamado para acciones recuperadas")


def test_chat_route_explicit_open_does_not_go_to_main_model():
    gateway = Gateway(
        response_controller=ResponseController(main_model=ExplodingMainModel()),
    )

    response = gateway.handle_message("abre Figma", debug=True)

    assert response.route != "chat"
    assert response.debug["action_intent_guard"]["action_required"] is True
    assert response.debug["action_intent_guard"]["target"] == "Figma"


def test_conceptual_question_still_goes_to_chat():
    class FakeMainModel(MainModel):
        def respond(self, context):
            return "Google es un motor de búsqueda."

    gateway = Gateway(
        response_controller=ResponseController(main_model=FakeMainModel()),
    )

    response = gateway.handle_message("qué es Google", debug=True)

    assert response.status == "ok"
    assert response.route == "chat"
    assert "motor" in response.text.lower()
    assert response.debug["action_intent_guard"]["reason"] == "conceptual_question"


def test_vague_reference_still_handled_by_clarification_guard_not_action_guard():
    gateway = Gateway(
        response_controller=ResponseController(main_model=ExplodingMainModel()),
    )

    response = gateway.handle_message("ábrela", debug=True)

    assert response.status == "needs_clarification"
    assert response.route == "clarification"
    assert "action_intent_guard" not in response.debug
    assert response.debug["chat_clarification_guard"]["should_clarify"] is True
