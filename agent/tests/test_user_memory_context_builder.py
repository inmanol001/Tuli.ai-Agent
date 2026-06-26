from pathlib import Path

from agent.context_builder.builder import ContextBuilder
from agent.gateway.session_manager import SessionState
from agent.memory.sqlite_store import SQLiteStore
from agent.memory.user_memory import handle_explicit_memory_request
from agent.router.router_schema import RouterDecision


def test_context_builder_includes_user_memories(tmp_path: Path):
    store = SQLiteStore(tmp_path / "memory.db")

    handle_explicit_memory_request(
        store,
        "recuerda que prefiero respuestas directas",
    )

    decision = RouterDecision(
        intent="chat",
        domain="general",
        action="respond",
        route="chat",
        needs_tool=False,
    )

    context = ContextBuilder(learning_memory_store=store).build(
        "hola",
        decision,
        SessionState(session_id="s1"),
    )

    assert "user_memories" in context.session_state
    assert context.session_state["user_memories"][0]["value"] == "prefiero respuestas directas"
