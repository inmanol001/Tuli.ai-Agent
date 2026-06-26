from agent.context_builder.assembler import assemble_messages
from agent.gateway.message_types import ContextPackage
from agent.router.router_schema import RouterDecision


def _decision(route: str = "chat") -> RouterDecision:
    return RouterDecision(
        intent="chat",
        domain="general",
        action="respond",
        route=route,
        needs_tool=False,
        needs_clarification=False,
        missing_info=[],
        needs_memory=False,
        needs_rag=False,
        needs_vision=False,
        risk_level="low",
        suggested_plugins=[],
        suggested_skills=[],
        suggested_tools=[],
        context_needed=[],
    )


def _context(user_memories):
    return ContextPackage(
        system_prompt="system",
        user_message="¿cuándo es mi cumpleaños?",
        router_decision=_decision(),
        recent_history=[],
        session_state={
            "previous_route": None,
            "current_route": "chat",
            "pending_clarification": None,
            "pending_confirmation": None,
            "user_memories": user_memories,
        },
        behavior={},
        selected_plugins=[],
        selected_skills=[],
        selected_tools=[],
        rag_snippets=[],
        safety_rules=[],
        task_instruction="Answer clearly.",
    )


def test_assemble_messages_includes_user_memories():
    messages = assemble_messages(
        _context(
            [
                {
                    "memory_type": "personal_fact",
                    "key": "birthday",
                    "value": "mi cumpleaños es el 18 de febrero",
                },
                {
                    "memory_type": "preference",
                    "key": "preference",
                    "value": "prefiero respuestas directas",
                },
            ]
        )
    )

    joined = "\\n".join(message["content"] for message in messages)

    assert "User memories:" in joined
    assert "[personal_fact:birthday] mi cumpleaños es el 18 de febrero" in joined
    assert "[preference:preference] prefiero respuestas directas" in joined
    assert "Use these memories when they are relevant" in joined


def test_assemble_messages_handles_no_user_memories():
    messages = assemble_messages(_context([]))

    joined = "\\n".join(message["content"] for message in messages)

    assert "User memories:" in joined
    assert "(none)" in joined
