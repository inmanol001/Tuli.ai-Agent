from agent.clarification.context_resolver import ContextResolver
from agent.gateway.message_types import ContextPackage, ConversationTurn
from agent.router.router_schema import RouterDecision


def make_context(message: str, history: list[str] | None = None) -> ContextPackage:
    return ContextPackage(
        system_prompt="system",
        user_message=message,
        router_decision=RouterDecision(route="chat"),
        recent_history=[
            ConversationTurn(role="user", content=item)
            for item in (history or [])
        ],
    )


def resolve(message: str, history: list[str] | None = None):
    return ContextResolver().resolve(make_context(message, history))


def test_extracts_open_entity_from_working_with_pattern():
    result = resolve("ábrela", ["vamos a trabajar con Figma"])

    assert result.has_vague_reference is True
    assert result.confidence == "high"
    assert result.resolved_reference == "Figma"
    assert result.candidates == ["Figma"]


def test_extracts_open_entity_from_app_role_pattern():
    result = resolve("abre esa", ["la app será Notion"])

    assert result.has_vague_reference is True
    assert result.confidence == "high"
    assert result.resolved_reference == "Notion"
    assert result.candidates == ["Notion"]


def test_extracts_multiple_open_entities_from_options_pattern():
    result = resolve("abre esa", ["podemos usar Slack o Trello"])

    assert result.has_vague_reference is True
    assert result.confidence == "ambiguous"
    assert result.resolved_reference is None
    assert "Slack" in result.candidates
    assert "Trello" in result.candidates


def test_extracts_open_entity_from_editor_role_pattern():
    result = resolve("abre ese", ["el editor será VSCode"])

    assert result.has_vague_reference is True
    assert result.confidence == "high"
    assert result.resolved_reference == "VSCode"
    assert result.candidates == ["VSCode"]


def test_keeps_file_entity_resolution():
    result = resolve("corrige ese", ["el archivo principal es landing_page.md"])

    assert result.has_vague_reference is True
    assert result.confidence == "high"
    assert result.resolved_reference == "landing_page.md"
    assert result.candidates == ["landing_page.md"]


def test_explicit_platform_missing_content_does_not_resolve_platform():
    result = resolve("monta ese texto en Figma", [])

    assert result.has_vague_reference is True
    assert result.reason == "explicit_platform_missing_content"
    assert result.confidence == "none"
    assert result.resolved_reference is None
    assert result.candidates == []


def test_known_apps_still_work_as_fallback():
    result = resolve("ábrela", ["vamos a trabajar en Terminal"])

    assert result.has_vague_reference is True
    assert result.confidence == "high"
    assert result.resolved_reference == "Terminal"
