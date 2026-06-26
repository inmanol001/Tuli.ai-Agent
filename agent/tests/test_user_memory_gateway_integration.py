from pathlib import Path

from agent.gateway.gateway import Gateway
from agent.gateway.gateway_logger import GatewayLogger
from agent.gateway.session_manager import SessionManager
from agent.memory.sqlite_store import SQLiteStore
from agent.memory.user_memory import load_user_memories


class ExplodingRouter:
    def route(self, user_text: str):
        raise AssertionError("Router should not be called for explicit memory writes")


def test_gateway_writes_explicit_memory_before_router(tmp_path: Path):
    store = SQLiteStore(tmp_path / "memory.db")

    gateway = Gateway(
        session_manager=SessionManager(store=store),
        router=ExplodingRouter(),
        logger=GatewayLogger(tmp_path / "logs"),
    )

    response = gateway.handle_message(
        "recuerda que prefiero respuestas directas",
        debug=True,
    )

    assert response.status == "ok"
    assert response.route == "memory_lookup"
    assert "recordaré" in response.text
    assert response.debug["memory_write"] is True

    memories = load_user_memories(store)

    assert len(memories) == 1
    assert memories[0]["value"] == "prefiero respuestas directas"
    assert memories[0]["memory_type"] == "preference"
