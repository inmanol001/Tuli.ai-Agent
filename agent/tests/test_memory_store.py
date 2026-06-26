import sqlite3

from agent.memory.sqlite_store import SQLiteStore


def test_sqlite_store_creates_required_tables(tmp_path):
    db_path = tmp_path / "memory.db"
    assert not db_path.exists()
    SQLiteStore(db_path)
    assert db_path.exists()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()

    table_names = {row[0] for row in rows}
    assert "session_state" in table_names
    assert "conversation_turns" in table_names
    assert "preferences" in table_names
    assert "tool_memory" in table_names
    assert "error_memory" in table_names
    assert "conversation_summaries" in table_names


def test_sqlite_store_round_trips_session_and_turns(tmp_path):
    store = SQLiteStore(tmp_path / "memory.db")
    store.upsert_session_state(
        session_id="abc",
        previous_route="chat",
        current_route="clarification",
        pending_clarification="artist_or_genre",
        pending_confirmation={"message": "borra"},
        pending_workflow={"workflow_id": "wf-1", "checkpoint_id": "cp-1"},
    )
    store.append_turn("abc", "user", "hola")
    store.append_turn("abc", "assistant", "hola")

    state = store.get_session_state("abc")
    turns = store.load_recent_turns("abc", 10)

    assert state["pending_confirmation"] == {"message": "borra"}
    assert state["pending_clarification"] == "artist_or_genre"
    assert state["pending_workflow"] == {"workflow_id": "wf-1", "checkpoint_id": "cp-1"}
    assert [turn["content"] for turn in turns] == ["hola", "hola"]


def test_sqlite_store_preferences_tool_memory_and_error_memory(tmp_path):
    store = SQLiteStore(tmp_path / "memory.db")
    store.upsert_preference(
        key="language",
        value="es",
        confidence=1.0,
        source="explicit_user_message",
    )
    store.record_tool_result(
        tool_name="browser_search",
        success=True,
        input_data={"query": "omega", "target": "youtube"},
        result_summary="https://youtube.test",
    )
    store.record_tool_result(
        tool_name="browser_search",
        success=False,
        input_data={"query": ""},
        result_summary="missing query",
    )
    store.record_error(error="missing query", source="tool:browser_search")
    store.record_error(error="missing query", source="tool:browser_search")

    with store.connect() as conn:
        pref = conn.execute("SELECT * FROM preferences WHERE key = 'language'").fetchone()
        tool = conn.execute(
            "SELECT * FROM tool_memory WHERE tool_name = 'browser_search'"
        ).fetchone()
        error = conn.execute(
            "SELECT * FROM error_memory WHERE error = 'missing query'"
        ).fetchone()

    assert pref["value"] == "es"
    assert tool["success_count"] == 1
    assert tool["fail_count"] == 1
    assert error["count"] == 2
