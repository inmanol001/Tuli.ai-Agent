from agent.clarification.context_resolver import ContextResolver
from agent.gateway.message_types import ContextPackage, ConversationTurn
from agent.router.router_schema import RouterDecision


def make_context(message: str, history: list[ConversationTurn]) -> ContextPackage:
    return ContextPackage(
        system_prompt="system",
        user_message=message,
        router_decision=RouterDecision(route="chat"),
        recent_history=history,
    )


def test_assistant_question_does_not_become_pattern_entity():
    context = make_context(
        "ábrela",
        [
            ConversationTurn(role="user", content="vamos a trabajar con Figma"),
            ConversationTurn(
                role="assistant",
                content="¿Quieres crear un proyecto nuevo, editar un archivo existente o realizar una tarea específica en Figma?",
            ),
        ],
    )

    result = ContextResolver().resolve(context)

    assert result.confidence == "high"
    assert result.resolved_reference == "Figma"
    assert result.candidates == ["Figma"]
    assert "editar un archivo existente" not in result.candidates


def test_assistant_secondary_suggestion_does_not_pollute_user_options():
    context = make_context(
        "abre esa",
        [
            ConversationTurn(role="user", content="podemos usar Slack o Trello"),
            ConversationTurn(
                role="assistant",
                content="También puedes usar Google Workspace, Asana o Notion si prefieres.",
            ),
        ],
    )

    result = ContextResolver().resolve(context)

    assert result.confidence == "ambiguous"
    assert result.resolved_reference is None
    assert result.candidates == ["Slack", "Trello"]
    assert "Google" not in result.candidates
    assert "Notion" not in result.candidates
