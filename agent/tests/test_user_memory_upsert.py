from pathlib import Path

from agent.memory.sqlite_store import SQLiteStore
from agent.memory.user_memory import (
    handle_explicit_memory_request,
    load_user_memories,
    record_user_memory,
)


def test_record_user_memory_upserts_duplicate_value(tmp_path: Path):
    store = SQLiteStore(tmp_path / "memory.db")

    first = record_user_memory(
        store,
        source_phrase="recuerda que prefiero respuestas directas",
        value="prefiero respuestas directas",
        memory_type="preference",
        key="preference",
        confidence=0.80,
    )

    second = record_user_memory(
        store,
        source_phrase="para futuras conversaciones prefiero respuestas directas",
        value="prefiero respuestas directas",
        memory_type="preference",
        key="preference",
        confidence=0.88,
    )

    memories = load_user_memories(store)

    assert len(memories) == 1
    assert first["id"] == second["id"]
    assert memories[0]["confidence"] == 0.95
    assert memories[0]["status"] == "verified"
    assert memories[0]["trust_level"] == "trusted"
    assert memories[0]["verification_count"] == 2
    assert memories[0]["source_phrase"] == "para futuras conversaciones prefiero respuestas directas"


def test_explicit_memory_color_favorite_gets_personal_fact_key(tmp_path: Path):
    store = SQLiteStore(tmp_path / "memory.db")

    memory = handle_explicit_memory_request(
        store,
        "quiero que sepas que mi color favorito es el negro",
    )

    assert memory is not None
    assert memory["memory_type"] == "personal_fact"
    assert memory["key"] == "favorite_color"
    assert memory["value"] == "mi color favorito es el negro"


def test_repeated_semantic_memory_does_not_duplicate(tmp_path: Path):
    store = SQLiteStore(tmp_path / "memory.db")

    first = handle_explicit_memory_request(
        store,
        "quiero que sepas que mi cumpleaños es el 18 de febrero",
    )

    second = handle_explicit_memory_request(
        store,
        "quiero que sepas que mi cumpleaños es el 18 de febrero",
    )

    memories = load_user_memories(store)

    assert first is not None
    assert second is not None
    assert first["id"] == second["id"]
    assert len(memories) == 1
    assert memories[0]["key"] == "birthday"
