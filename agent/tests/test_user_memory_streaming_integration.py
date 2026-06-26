from pathlib import Path

from agent.gateway.gateway import Gateway
from agent.gateway.gateway_logger import GatewayLogger
from agent.gateway.session_manager import SessionManager
from agent.memory.sqlite_store import SQLiteStore
from agent.memory.user_memory import load_user_memories


class ExplodingRouter:
    def route(self, user_text: str):
        raise AssertionError("Router should not be called for explicit memory writes")


def test_stream_message_writes_explicit_memory_before_router(tmp_path: Path):
    store = SQLiteStore(tmp_path / "memory.db")

    gateway = Gateway(
        session_manager=SessionManager(store=store),
        router=ExplodingRouter(),
        logger=GatewayLogger(tmp_path / "logs"),
    )

    events = list(
        gateway.stream_message(
            "recuerda que mi cumpleaños es el 18 de febrero",
            debug=True,
        )
    )

    response_events = [event for event in events if event.get("type") == "response"]

    assert response_events
    assert response_events[0]["response"].status == "ok"
    assert response_events[0]["response"].route == "memory_lookup"
    assert "recordaré" in response_events[0]["response"].text

    memories = load_user_memories(store)

    assert len(memories) == 1
    assert memories[0]["value"] == "mi cumpleaños es el 18 de febrero"
    assert memories[0]["status"] == "active"
