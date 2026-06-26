from agent.clarification.builder import ClarificationBuilder
from agent.gateway.message_types import ContextPackage, ConversationTurn
from agent.router.router_schema import RouterDecision


def make_context(
    user_message: str,
    *,
    missing_info: list[str] | None = None,
    pending_clarification: str | None = None,
    domain: str = "browser",
    action: str = "search",
) -> ContextPackage:
    return ContextPackage(
        system_prompt="system",
        user_message=user_message,
        router_decision=RouterDecision(
            intent="action",
            domain=domain,
            action=action,
            route="clarification",
            needs_tool=True,
            needs_clarification=True,
            missing_info=missing_info or [],
        ),
        session_state={"pending_clarification": pending_clarification},
    )


def test_clarification_builder_handles_recent_tool_confirmation_question():
    result = ClarificationBuilder().build(make_context("ya abriste GitHub?"))

    assert result.text.startswith(
        "No puedo confirmarlo porque no tengo un `tool_result` reciente de GitHub"
    )
    assert "Opciones:" in result.text
    assert "1." in result.text and "2." in result.text and "3." in result.text
    assert "Qué detalle te falta" not in result.text


def test_clarification_builder_handles_open_reference():
    result = ClarificationBuilder().build(make_context("abre eso", action="open_app"))

    assert "qué quieres abrir" in result.text.lower()
    assert "Opciones:" in result.text
    assert "1." in result.text


def test_clarification_builder_handles_search_reference():
    result = ClarificationBuilder().build(make_context("búscame eso"))

    assert "qué tema quieres" in result.text.lower()
    assert "Opciones:" in result.text
    assert "1." in result.text


def test_clarification_builder_handles_previous_action_reference():
    result = ClarificationBuilder().build(make_context("hazlo como la vez pasada"))

    assert "acción anterior" in result.text.lower()
    assert "Opciones:" in result.text
    assert "1." in result.text


def test_clarification_builder_handles_list_item_reference():
    result = ClarificationBuilder().build(make_context("muéstrame el primero"))

    assert "lista reciente" in result.text.lower() or "el primero" in result.text.lower()
    assert "Opciones:" in result.text
    assert "1." in result.text


def test_clarification_builder_uses_missing_info_for_design():
    result = ClarificationBuilder().build(
        make_context(
            "haz un diseño",
            missing_info=["format", "style", "platform"],
            domain="design",
            action="design",
        )
    )

    assert "post cuadrado" in result.text.lower()
    assert "estilo elegante" in result.text.lower()
    assert "en qué plataforma" in result.text.lower()
    assert result.pending_clarification == "format"


def test_clarification_builder_uses_real_candidates_for_resolved_reference_confirmation():
    context = ContextPackage(
        system_prompt="system",
        user_message="ábrela",
        router_decision=RouterDecision(
            intent="action",
            domain="browser",
            action="browser_search",
            route="clarification",
            needs_tool=True,
            needs_clarification=True,
            missing_info=["resolved_reference_confirmation"],
        ),
        recent_history=[
            ConversationTurn(role="user", content="vamos a trabajar con Canva"),
        ],
        session_state={"pending_clarification": "resolved_reference_confirmation"},
    )
    result = ClarificationBuilder().build(
        context,
        missing_info_override=["resolved_reference_confirmation"],
        reason_hint="resolved_reference_confirmation",
    )

    assert "Canva" in result.text
    assert "Sí, abrir Canva" in result.text
    assert "último sitio mencionado" not in result.text.lower()
    assert "último contexto disponible" not in result.text.lower()


def test_clarification_builder_uses_real_candidates_for_ambiguous_reference():
    context = ContextPackage(
        system_prompt="system",
        user_message="ábrela",
        router_decision=RouterDecision(
            intent="action",
            domain="browser",
            action="browser_search",
            route="clarification",
            needs_tool=True,
            needs_clarification=True,
            missing_info=["ambiguous_reference"],
        ),
        recent_history=[
            ConversationTurn(role="user", content="tenemos dos opciones: Canva y GitHub"),
        ],
        session_state={"pending_clarification": "ambiguous_reference"},
    )
    result = ClarificationBuilder().build(
        context,
        missing_info_override=["ambiguous_reference"],
        reason_hint="ambiguous_reference",
    )

    assert "Canva" in result.text
    assert "GitHub" in result.text
    assert "Otra cosa" in result.text


def test_clarification_builder_uses_target_content_with_platform_context():
    context = ContextPackage(
        system_prompt="system",
        user_message="monta ese texto en Canva",
        router_decision=RouterDecision(
            intent="action",
            domain="workflow",
            action="full_workflow_candidate",
            route="clarification",
            needs_tool=True,
            needs_clarification=True,
            missing_info=["target_content"],
        ),
        session_state={"pending_clarification": "target_content"},
    )
    result = ClarificationBuilder().build(
        context,
        missing_info_override=["target_content"],
        reason_hint="explicit_platform_missing_content",
    )

    assert "Canva" in result.text
    assert "qué contenido" in result.text.lower()
    assert result.pending_clarification == "target_content"
