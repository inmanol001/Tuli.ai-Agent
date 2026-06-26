from agent.clarification.context_resolver import ContextResolver
from agent.gateway.message_types import ContextPackage, ConversationTurn
from agent.router.router_schema import RouterDecision


def make_context(user_message: str, recent_history=None) -> ContextPackage:
    return ContextPackage(
        system_prompt="system",
        user_message=user_message,
        router_decision=RouterDecision(route="chat"),
        recent_history=recent_history or [],
    )


def test_context_resolver_single_entity():
    context = make_context(
        "ábrela",
        recent_history=[ConversationTurn(role="user", content="vamos a trabajar con Canva")],
    )
    result = ContextResolver().resolve(context)

    assert result.has_vague_reference is True
    assert result.resolved_reference == "Canva"
    assert result.confidence == "high"
    assert result.candidates == ["Canva"]


def test_context_resolver_multiple_entities():
    context = make_context(
        "ábrela",
        recent_history=[
            ConversationTurn(role="user", content="tenemos dos opciones: Canva y GitHub"),
        ],
    )
    result = ContextResolver().resolve(context)

    assert result.has_vague_reference is True
    assert result.resolved_reference is None
    assert result.confidence == "ambiguous"
    assert "Canva" in result.candidates
    assert "GitHub" in result.candidates


def test_context_resolver_recent_tool_result():
    context = make_context(
        "quedó abierta?",
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
    result = ContextResolver().resolve(context)

    assert result.has_status_question is True
    assert result.recent_tool_result is not None
    assert result.confidence == "high"
    assert result.reason == "recent_tool_result_available"


def test_context_resolver_recent_tool_result_with_flexible_phrase():
    context = make_context(
        "la página quedó abierta?",
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
    result = ContextResolver().resolve(context)

    assert result.has_status_question is True
    assert result.recent_tool_result is not None
    assert result.confidence == "high"
    assert result.reason == "recent_tool_result_available"


def test_context_resolver_status_question_without_tool_result():
    context = make_context("se aplicó el cambio?")
    result = ContextResolver().resolve(context)

    assert result.has_status_question is True
    assert result.recent_tool_result is None
    assert result.confidence == "none"
    assert result.reason == "missing_recent_tool_result"


def test_context_resolver_explicit_platform_missing_content():
    context = make_context("monta ese texto en Canva")
    result = ContextResolver().resolve(context)

    assert result.has_vague_reference is True
    assert result.reason == "explicit_platform_missing_content"
    assert result.resolved_reference is None
    assert result.candidates == []
    assert result.confidence == "none"


def test_context_resolver_no_context():
    context = make_context("ábrela")
    result = ContextResolver().resolve(context)

    assert result.has_vague_reference is True
    assert result.confidence == "none"
    assert result.candidates == []


def test_context_resolver_detects_file_entity():
    context = make_context(
        "corrige la parte que falla",
        recent_history=[
            ConversationTurn(role="user", content="el error está en router_validator.py")
        ],
    )
    result = ContextResolver().resolve(context)

    assert any(entity.value == "router_validator.py" for entity in result.entities)
