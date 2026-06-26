from pathlib import Path

from agent.memory.sqlite_store import SQLiteStore
from agent.memory.user_memory import (
    handle_explicit_memory_request,
    load_relevant_user_memories,
)


def test_load_relevant_user_memories_returns_active_memories(tmp_path: Path):
    store = SQLiteStore(tmp_path / "memory.db")

    handle_explicit_memory_request(
        store,
        "recuerda que prefiero respuestas directas",
    )

    memories = load_relevant_user_memories(
        store,
        user_message="hola",
    )

    assert len(memories) == 1
    assert memories[0]["value"] == "prefiero respuestas directas"
    assert memories[0]["memory_type"] == "preference"


def test_load_relevant_user_memories_prefers_matching_terms(tmp_path: Path):
    store = SQLiteStore(tmp_path / "memory.db")

    handle_explicit_memory_request(
        store,
        "recuerda que cuando diga diseño floral me refiero a Ysis Sánchez",
    )
    handle_explicit_memory_request(
        store,
        "recuerda que prefiero respuestas directas",
    )

    memories = load_relevant_user_memories(
        store,
        user_message="haz un diseño floral",
    )

    values = [memory["value"] for memory in memories]

    assert any("diseño floral" in value for value in values)
