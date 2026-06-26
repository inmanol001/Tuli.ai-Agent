from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or "agent/memory/memory.db")
        self.schema_path = Path(__file__).with_name("schema.sql")
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        schema = self.schema_path.read_text(encoding="utf-8")
        with self.connect() as conn:
            conn.executescript(schema)
            self._ensure_column(conn, "session_state", "pending_workflow_json", "TEXT")

    def get_session_state(self, session_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM session_state WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        pending_json = data.pop("pending_confirmation_json", None)
        pending_workflow_json = data.pop("pending_workflow_json", None)
        data["pending_confirmation"] = (
            json.loads(pending_json) if pending_json else None
        )
        data["pending_workflow"] = (
            json.loads(pending_workflow_json) if pending_workflow_json else None
        )
        return data

    def upsert_session_state(
        self,
        *,
        session_id: str,
        previous_route: str | None,
        current_route: str | None,
        pending_clarification: str | None,
        pending_confirmation: dict[str, Any] | None,
        pending_workflow: dict[str, Any] | None,
    ) -> None:
        now = utc_now()
        pending_json = (
            json.dumps(pending_confirmation, ensure_ascii=True)
            if pending_confirmation is not None
            else None
        )
        pending_workflow_json = (
            json.dumps(pending_workflow, ensure_ascii=True)
            if pending_workflow is not None
            else None
        )
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO session_state (
                    session_id, previous_route, current_route,
                    pending_clarification, pending_confirmation_json,
                    pending_workflow_json,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    previous_route = excluded.previous_route,
                    current_route = excluded.current_route,
                    pending_clarification = excluded.pending_clarification,
                    pending_confirmation_json = excluded.pending_confirmation_json,
                    pending_workflow_json = excluded.pending_workflow_json,
                    updated_at = excluded.updated_at
                """,
                (
                    session_id,
                    previous_route,
                    current_route,
                    pending_clarification,
                    pending_json,
                    pending_workflow_json,
                    now,
                    now,
                ),
            )

    def append_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        metadata_json = (
            json.dumps(metadata, ensure_ascii=True) if metadata is not None else None
        )
        now = utc_now()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(turn_index), -1) + 1 AS next_index "
                "FROM conversation_turns WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            turn_index = int(row["next_index"])
            conn.execute(
                """
                INSERT INTO conversation_turns (
                    session_id, turn_index, role, content, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, turn_index, role, content, metadata_json, now),
            )
        return turn_index

    def load_recent_turns(self, session_id: str, limit: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, metadata_json, turn_index, created_at
                FROM conversation_turns
                WHERE session_id = ?
                ORDER BY turn_index DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        turns = [dict(row) for row in reversed(rows)]
        for turn in turns:
            metadata_json = turn.get("metadata_json")
            turn["metadata"] = json.loads(metadata_json) if metadata_json else None
        return turns

    def upsert_preference(
        self,
        *,
        key: str,
        value: str,
        confidence: float,
        source: str,
    ) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO preferences (key, value, confidence, source, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    confidence = excluded.confidence,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                (key, value, confidence, source, now),
            )

    def load_preferences(self, limit: int = 3) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT key, value, confidence, source, updated_at
                FROM preferences
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_tool_result(
        self,
        *,
        tool_name: str,
        success: bool,
        input_data: dict[str, Any] | None,
        result_summary: str | None,
        notes: str | None = None,
    ) -> None:
        now = utc_now()
        input_json = (
            json.dumps(input_data, ensure_ascii=True) if input_data is not None else None
        )
        success_inc = 1 if success else 0
        fail_inc = 0 if success else 1
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO tool_memory (
                    tool_name, notes, success_count, fail_count,
                    last_input_json, last_result_summary, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tool_name) DO UPDATE SET
                    notes = COALESCE(excluded.notes, tool_memory.notes),
                    success_count = tool_memory.success_count + ?,
                    fail_count = tool_memory.fail_count + ?,
                    last_input_json = excluded.last_input_json,
                    last_result_summary = excluded.last_result_summary,
                    updated_at = excluded.updated_at
                """,
                (
                    tool_name,
                    notes,
                    success_inc,
                    fail_inc,
                    input_json,
                    result_summary,
                    now,
                    success_inc,
                    fail_inc,
                ),
            )

    def record_error(
        self,
        *,
        error: str,
        source: str,
        solution: str | None = None,
    ) -> None:
        now = utc_now()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id, count FROM error_memory WHERE error = ? AND source = ?",
                (error, source),
            ).fetchone()
            if row:
                conn.execute(
                    """
                    UPDATE error_memory
                    SET count = ?, solution = COALESCE(?, solution), updated_at = ?
                    WHERE id = ?
                    """,
                    (int(row["count"]) + 1, solution, now, row["id"]),
                )
                return
            conn.execute(
                """
                INSERT INTO error_memory (error, solution, source, count, updated_at)
                VALUES (?, ?, ?, 1, ?)
                """,
                (error, solution, source, now),
            )

    def insert_summary(self, session_id: str, summary: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO conversation_summaries (session_id, summary, created_at)
                VALUES (?, ?, ?)
                """,
                (session_id, summary, utc_now()),
            )

    def _ensure_column(
        self,
        conn: sqlite3.Connection,
        table: str,
        column: str,
        column_type: str,
    ) -> None:
        columns = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column in columns:
            return
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
