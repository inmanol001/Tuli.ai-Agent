from pathlib import Path

from agent.memory.sqlite_store import SQLiteStore
from agent.memory.user_memory import (
    load_relevant_user_memories,
    record_user_memory,
)


def test_relevant_user_memories_include_birthday_for_birthday_question(tmp_path: Path):
    store = SQLiteStore(tmp_path / "memory.db")

    record_user_memory(
        store,
        source_phrase="para futuras conversaciones prefiero respuestas directas",
        value="prefiero respuestas directas",
        memory_type="preference",
        key="preference",
        confidence=0.88,
    )
    record_user_memory(
        store,
        source_phrase="quiero que sepas que mi cumpleaños es el 18 de febrero",
        value="mi cumpleaños es el 18 de febrero",
        memory_type="personal_fact",
        key="birthday",
        confidence=0.88,
    )

    memories = load_relevant_user_memories(
        store,
        user_message="cuándo es mi cumpleaños?",
    )

    assert memories
    assert any(memory["key"] == "birthday" for memory in memories)
    assert memories[0]["key"] == "birthday"


def test_relevant_user_memories_include_stable_facts_even_without_exact_match(tmp_path: Path):
    store = SQLiteStore(tmp_path / "memory.db")

    record_user_memory(
        store,
        source_phrase="quiero que sepas que mi color favorito es el negro",
        value="mi color favorito es el negro",
        memory_type="personal_fact",
        key="favorite_color",
        confidence=0.88,
    )

    memories = load_relevant_user_memories(
        store,
        user_message="hola",
    )

    assert any(memory["key"] == "favorite_color" for memory in memories)
