from __future__ import annotations

import json
from typing import Any

from agent.conversation_state.state import default_conversation_state, normalize_conversation_state


def ensure_conversation_state_table(store: Any) -> None:
    with store.connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_state (
                session_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def load_conversation_state(store: Any, session_id: str) -> dict[str, Any]:
    ensure_conversation_state_table(store)
    with store.connect() as conn:
        row = conn.execute(
            "SELECT state_json FROM conversation_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()

    if row is None:
        return default_conversation_state()

    try:
        raw = row["state_json"] if isinstance(row, dict) else row[0]
        return normalize_conversation_state(json.loads(raw))
    except Exception:
        return default_conversation_state()


def save_conversation_state(store: Any, session_id: str, state: dict[str, Any]) -> None:
    ensure_conversation_state_table(store)
    normalized = normalize_conversation_state(state)
    payload = json.dumps(normalized, ensure_ascii=False)
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO conversation_state (session_id, state_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(session_id) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (session_id, payload),
        )
        conn.commit()
