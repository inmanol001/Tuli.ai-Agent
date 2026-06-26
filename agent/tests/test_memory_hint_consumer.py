from agent.context_builder.builder import ContextBuilder
from agent.gateway.session_manager import SessionState
from agent.memory.learning_memory import record_learning_memory
from agent.memory.sqlite_store import SQLiteStore
from agent.router.router_schema import RouterDecision


def test_learning_hint_candidate_adds_correct_tool_to_context(tmp_path):
    store = SQLiteStore(tmp_path / "memory.db")

    for _ in range(2):
        record_learning_memory(
            store,
            user_phrase="abre figma",
            correct_intent="action",
            correct_tool="open_app",
            correct_skill="open_app",
            status="temporary",
            confidence=0.65,
        )

    decision = RouterDecision(
        intent="action",
        domain="general",
        action="respond",
        route="chat",
        needs_tool=False,
        suggested_tools=["web_search"],
    )

    context = ContextBuilder(learning_memory_store=store).build(
        "abre figma",
        decision,
        SessionState(session_id="s1"),
    )

    tool_names = [tool["name"] for tool in context.selected_tools]
    skill_names = [skill["name"] for skill in context.selected_skills]

    assert context.router_decision.route == "chat"
    assert "web_search" in tool_names
    assert "open_app" in tool_names
    assert "open_app" in skill_names
    assert context.session_state["learning_hints"][0]["correct_tool"] == "open_app"


def test_temporary_hint_does_not_add_tool_to_context(tmp_path):
    store = SQLiteStore(tmp_path / "memory.db")

    record_learning_memory(
        store,
        user_phrase="abre capcut",
        correct_intent="action",
        correct_tool="open_app",
        correct_skill="open_app",
        status="temporary",
        confidence=0.65,
    )

    decision = RouterDecision(
        intent="action",
        domain="general",
        action="respond",
        route="chat",
        needs_tool=False,
        suggested_tools=["web_search"],
    )

    context = ContextBuilder(learning_memory_store=store).build(
        "abre capcut",
        decision,
        SessionState(session_id="s1"),
    )

    tool_names = [tool["name"] for tool in context.selected_tools]

    assert context.session_state["learning_hints"] == []
    assert tool_names == ["web_search"]


def test_learning_hint_dedupes_existing_tool(tmp_path):
    store = SQLiteStore(tmp_path / "memory.db")

    for _ in range(2):
        record_learning_memory(
            store,
            user_phrase="abre figma",
            correct_intent="action",
            correct_tool="open_app",
            correct_skill="open_app",
            status="temporary",
            confidence=0.65,
        )

    decision = RouterDecision(
        intent="action",
        domain="macos",
        action="open_app",
        route="action_ready",
        needs_tool=True,
        suggested_skills=["open_app"],
        suggested_tools=["open_app"],
    )

    context = ContextBuilder(learning_memory_store=store).build(
        "abre figma",
        decision,
        SessionState(session_id="s1"),
    )

    tool_names = [tool["name"] for tool in context.selected_tools]
    skill_names = [skill["name"] for skill in context.selected_skills]

    assert tool_names.count("open_app") == 1
    assert skill_names.count("open_app") == 1
