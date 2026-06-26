import sqlite3

from agent.memory.sqlite_store import SQLiteStore
from agent.memory.learning_memory import (
    load_learning_memory,
    record_learning_memory,
    verify_learning_memory,
    deprecate_learning_memory,
)


def test_learning_memory_records_and_promotes_candidate(tmp_path):
    db_path = tmp_path / "memory.sqlite3"
    store = SQLiteStore(str(db_path))

    record_learning_memory(
        store,
        user_phrase="abre el primero",
        correct_intent="action",
        correct_tool="browser_search",
        correct_skill="browser_search",
        confidence=0.7,
        evidence={"tool_result": {"success": True}},
    )

    rows = load_learning_memory(store, phrase="abre el primero")
    assert len(rows) == 1
    assert rows[0]["status"] == "temporary"
    assert rows[0]["success_count"] == 1

    record_learning_memory(
        store,
        user_phrase="abre el primero",
        correct_intent="action",
        correct_tool="browser_search",
        correct_skill="browser_search",
        confidence=0.8,
        evidence={"tool_result": {"success": True}},
    )

    rows = load_learning_memory(store, phrase="abre el primero")
    assert len(rows) == 1
    assert rows[0]["status"] == "candidate"
    assert rows[0]["usage_count"] == 2
    assert rows[0]["success_count"] == 2


def test_learning_memory_verify_and_deprecate(tmp_path):
    db_path = tmp_path / "memory.sqlite3"
    store = SQLiteStore(str(db_path))

    record_learning_memory(
        store,
        user_phrase="activa mission control",
        correct_intent="action",
        correct_tool="macos_space_mission_control",
        correct_skill="macos_spaces",
        confidence=0.6,
    )

    row = load_learning_memory(store, phrase="activa mission control")[0]

    verify_learning_memory(store, row["id"])
    verified = load_learning_memory(store, phrase="activa mission control")[0]
    assert verified["status"] == "verified"
    assert verified["confidence"] >= 0.95
    assert verified["verified_at"] is not None

    deprecate_learning_memory(store, row["id"], notes="replaced by better mapping")
    deprecated = load_learning_memory(store, phrase="activa mission control")[0]
    assert deprecated["status"] == "deprecated"
    assert "replaced" in deprecated["notes"]


def test_learning_memory_table_exists_in_schema(tmp_path):
    db_path = tmp_path / "memory.sqlite3"
    store = SQLiteStore(str(db_path))

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert "learning_memory" in tables
