from pathlib import Path

from agent.memory.sqlite_store import SQLiteStore
from agent.memory.user_memory import handle_explicit_memory_request, load_user_memories


def test_handle_explicit_memory_request_uses_semantic_classifier(tmp_path: Path):
    store = SQLiteStore(tmp_path / "memory.db")

    memory = handle_explicit_memory_request(
        store,
        "quiero que sepas que mi cumpleaños es el 18 de febrero",
    )

    assert memory is not None
    assert memory["value"] == "mi cumpleaños es el 18 de febrero"
    assert memory["memory_type"] == "personal_fact"
    assert memory["key"] == "birthday"

    memories = load_user_memories(store)
    assert len(memories) == 1


def test_handle_explicit_memory_request_does_not_save_casual_text(tmp_path: Path):
    store = SQLiteStore(tmp_path / "memory.db")

    memory = handle_explicit_memory_request(
        store,
        "me gusta Figma",
    )

    assert memory is None
    assert load_user_memories(store) == []
