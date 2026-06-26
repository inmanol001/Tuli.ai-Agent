from agent.context_builder.builder import ContextBuilder
from agent.gateway.session_manager import SessionState
from agent.memory.learning_memory import (
    record_learning_memory,
    verify_learning_memory,
)
from agent.memory.memory_reader import load_relevant_learning_hints
from agent.memory.sqlite_store import SQLiteStore
from agent.router.router_schema import RouterDecision


def test_memory_reader_ignores_temporary(tmp_path):
    store = SQLiteStore(tmp_path / "memory.db")

    record_learning_memory(
        store,
        user_phrase="abre figma",
        correct_intent="action",
        correct_tool="open_app",
        correct_skill="open_app",
        status="temporary",
        confidence=0.65,
    )

    hints = load_relevant_learning_hints(store, user_message="abre figma")

    assert hints == []


def test_memory_reader_returns_candidate_after_repeated_success(tmp_path):
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

    hints = load_relevant_learning_hints(store, user_message="abre figma")

    assert len(hints) == 1
    assert hints[0]["status"] == "candidate"
    assert hints[0]["correct_tool"] == "open_app"


def test_memory_reader_returns_verified(tmp_path):
    store = SQLiteStore(tmp_path / "memory.db")

    record_learning_memory(
        store,
        user_phrase="abre figma",
        correct_intent="action",
        correct_tool="open_app",
        correct_skill="open_app",
        status="temporary",
        confidence=0.65,
    )

    with store.connect() as conn:
        memory_id = conn.execute(
            "SELECT id FROM learning_memory WHERE normalized_phrase = ?",
            ("abre figma",),
        ).fetchone()["id"]

    verify_learning_memory(store, memory_id)

    hints = load_relevant_learning_hints(store, user_message="abre figma")

    assert len(hints) == 1
    assert hints[0]["status"] == "verified"
    assert hints[0]["confidence"] >= 0.95


def test_context_builder_injects_learning_hints_into_session_state(tmp_path):
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

    context = ContextBuilder(learning_memory_store=store).build(
        "abre figma",
        RouterDecision(route="action_ready"),
        SessionState(session_id="test-session"),
    )

    hints = context.session_state["learning_hints"]

    assert len(hints) == 1
    assert hints[0]["correct_tool"] == "open_app"
    assert hints[0]["status"] == "candidate"
