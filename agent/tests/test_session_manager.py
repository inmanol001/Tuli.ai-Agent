from agent.gateway.session_manager import SessionManager
from agent.memory.sqlite_store import SQLiteStore


def make_manager(tmp_path, max_history=12):
    return SessionManager(
        max_history=max_history,
        store=SQLiteStore(tmp_path / "memory.db"),
    )


def test_session_manager_keeps_recent_history(tmp_path):
    manager = make_manager(tmp_path, max_history=2)
    session = manager.get_or_create("abc")
    manager.add_turn(session.session_id, "user", "hola")
    manager.add_turn(session.session_id, "assistant", "hola")
    manager.add_turn(session.session_id, "user", "otra")
    stored = manager.get_or_create("abc")
    assert stored.session_id == "abc"
    assert len(stored.history) == 2
    assert stored.history[-1].content == "otra"


def test_session_state_tracks_previous_and_current_route(tmp_path):
    manager = make_manager(tmp_path)
    session = manager.get_or_create("abc")
    session.previous_route = "clarification"
    session.current_route = "action_ready"
    stored = manager.get_or_create("abc")
    assert stored.previous_route == "clarification"
    assert stored.current_route == "action_ready"


def test_session_manager_rehydrates_state_and_history(tmp_path):
    store = SQLiteStore(tmp_path / "memory.db")
    first_manager = SessionManager(max_history=3, store=store)
    session = first_manager.get_or_create("persisted")
    session.pending_clarification = "artist_or_genre"
    session.previous_route = "chat"
    session.current_route = "clarification"
    first_manager.add_turn(session.session_id, "user", "busca musica en YouTube")
    first_manager.save_session_state(session.session_id)

    second_manager = SessionManager(max_history=3, store=store)
    restored = second_manager.get_or_create("persisted")

    assert restored.session_id == "persisted"
    assert restored.pending_clarification == "artist_or_genre"
    assert restored.previous_route == "chat"
    assert restored.current_route == "clarification"
    assert restored.history[-1].content == "busca musica en YouTube"
