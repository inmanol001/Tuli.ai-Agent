from pathlib import Path

from agent.memory.sqlite_store import SQLiteStore
from agent.memory.user_memory import (
    detect_explicit_memory_request,
    handle_explicit_memory_request,
    load_user_memories,
)


def test_detects_recuerda_que():
    request = detect_explicit_memory_request("recuerda que prefiero respuestas cortas")

    assert request is not None
    assert request.value == "prefiero respuestas cortas"
    assert request.memory_type == "preference"


def test_ignores_casual_text():
    assert detect_explicit_memory_request("me gusta figma") is None
    assert detect_explicit_memory_request("hola cómo estás") is None


def test_records_user_memory(tmp_path: Path):
    store = SQLiteStore(tmp_path / "memory.db")

    memory = handle_explicit_memory_request(
        store,
        "recuerda que mi agente actual se llama Tuli",
    )

    assert memory is not None
    assert memory["status"] == "active"
    assert memory["memory_type"] == "project"
    assert memory["value"] == "mi agente actual se llama Tuli"

    memories = load_user_memories(store)
    assert len(memories) == 1
    assert memories[0]["value"] == "mi agente actual se llama Tuli"
