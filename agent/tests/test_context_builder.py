from agent.context_builder.builder import ContextBuilder
from agent.context_builder.assembler import assemble_messages
from agent.gateway.message_types import ConversationTurn
from agent.gateway.session_manager import SessionState
from agent.router.router_schema import RouterDecision


class FakeRagRetriever:
    def __init__(self, snippets):
        self.snippets = snippets
        self.calls = []

    def retrieve(self, query):
        self.calls.append(query)
        return self.snippets


def test_context_excludes_rag_screenshots_and_desktop_tools():
    decision = RouterDecision(
        intent="action",
        domain="browser",
        action="search",
        route="action_ready",
        needs_tool=True,
        suggested_plugins=["browser"],
        suggested_skills=["browser_search"],
        suggested_tools=["browser_search", "take_screenshot", "click"],
    )
    context = ContextBuilder().build(
        "busca omega en youtube",
        decision,
        SessionState(session_id="s1"),
    )
    assert [plugin["name"] for plugin in context.selected_plugins] == ["browser"]
    assert [skill["name"] for skill in context.selected_skills] == ["browser_search"]
    assert [tool["name"] for tool in context.selected_tools] == ["browser_search"]
    assert context.router_decision.needs_rag is False
    assert context.router_decision.needs_vision is False
    assert "fixed macOS window tools" in context.system_prompt
    assert "fixed macOS Spaces tools may be executed" in context.system_prompt
    assert any("No screenshots" in rule for rule in context.safety_rules)
    assert any(
        "perform browser-based information searches" in rule
        for rule in context.safety_rules
    )
    assert any(
        "window_native_tiling may only act on the frontmost window" in rule
        for rule in context.safety_rules
    )
    assert any("macOS observation tools" in rule for rule in context.safety_rules)
    assert (
        "Use browser_search for browser-based navigation, information search, known web destinations, and direct http/https URLs."
        in context.task_instruction
    )
    assert "Use window_native_tiling for moving, centering, filling, or resizing the frontmost macOS window with fixed native menu actions." in context.task_instruction


def test_context_filters_duplicate_current_user_message():
    session = SessionState(session_id="s1")
    session.history.append(
        ConversationTurn(role="user", content="busca música en YouTube")
    )
    decision = RouterDecision(route="clarification")
    context = ContextBuilder().build("busca música en YouTube", decision, session)
    assert context.recent_history == []


def test_assembler_includes_history_and_session_state():
    session = SessionState(
        session_id="s1",
        history=[
            ConversationTurn(role="user", content="hola"),
            ConversationTurn(role="assistant", content="hola"),
        ],
        pending_clarification="artist_or_genre",
        pending_confirmation={"message": "borra eso"},
        previous_route="clarification",
        current_route="chat",
    )
    context = ContextBuilder().build("omega", RouterDecision(route="chat"), session)
    messages = assemble_messages(context)
    system_payload = messages[1]["content"]
    assert "Previous route: clarification" in system_payload
    assert "Current route: chat" in system_payload
    assert "Pending clarification: artist_or_genre" in system_payload
    assert "user: hola" in system_payload
    assert "selected_tools" not in system_payload


def test_context_omits_capabilities_when_router_does_not_request_them():
    session = SessionState(session_id="s1")
    context = ContextBuilder().build("hola", RouterDecision(route="chat"), session)
    assert context.selected_plugins == []
    assert context.selected_skills == []
    assert context.selected_tools == []
    assert context.rag_snippets == []


def test_context_includes_rag_snippets_only_when_requested():
    retriever = FakeRagRetriever(
        [
            {"source": "agent/knowledge/docs/json.md", "text": "JSON usa claves.", "score": 0.9},
            {"source": "agent/knowledge/docs/json.md", "text": "Segundo fragmento.", "score": 0.8},
            {"source": "agent/knowledge/docs/json.md", "text": "Tercer fragmento.", "score": 0.7},
            {"source": "agent/knowledge/docs/json.md", "text": "Cuarto fragmento.", "score": 0.6},
        ]
    )
    decision = RouterDecision(intent="rag", route="rag_lookup", needs_rag=True)
    context = ContextBuilder(rag_retriever=retriever).build(
        "según mis notas sobre JSON",
        decision,
        SessionState(session_id="s1"),
    )
    messages = assemble_messages(context)
    assert retriever.calls == ["según mis notas sobre JSON"]
    assert len(context.rag_snippets) == 3
    assert "RAG snippets:" in messages[1]["content"]
    assert "JSON usa claves." in messages[1]["content"]
