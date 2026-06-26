from agent.gateway.gateway import Gateway
from agent.models.main_model import MainModel
from agent.response_action.controller import ResponseController


class FakeMainModel(MainModel):
    def respond(self, context):
        return "Respuesta MVP"


def test_action_ready_resolved_reference_becomes_clarification():
    gateway = Gateway(
        response_controller=ResponseController(main_model=FakeMainModel()),
    )

    first = gateway.handle_message("el archivo principal es landing_page.md")
    second = gateway.handle_message("corrige ese", session_id=first.session_id, debug=True)

    assert second.status == "needs_clarification"
    assert second.route == "clarification"
    assert "landing_page.md" in second.text
    assert second.debug["context_resolution"]["resolved_reference"] == "landing_page.md"
    assert "tool_planner" not in second.debug
